import logging
import sqlite3
import os
import time
import uuid
from pathlib import Path
from collections import defaultdict, deque
from typing import Optional, Dict, Deque

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from google import genai

from evaluator import evaluate_with_retry
from models import AnswerRequest, InterviewEvaluation
from storage import (
    init_db,
    save_evaluation,
    get_session_history,
    get_candidate_history,
    get_candidate_summary,
    ensure_candidate_access,
    create_session,
    authorize_session,
    authorize_candidate,
)

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO")
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Interview Preparation OS",
    version="0.4.0"
)

DEFAULT_CORS_ORIGINS = [
    "https://ai-based-interview-simulator-1.onrender.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]

cors_origins_env = os.getenv(
    "CORS_ORIGINS",
    ""
).strip()

if cors_origins_env:
    CORS_ORIGINS = [
        origin.strip().rstrip("/")
        for origin in cors_origins_env.split(",")
        if origin.strip()
    ]
else:
    CORS_ORIGINS = DEFAULT_CORS_ORIGINS

logger.info(
    "Configured CORS origins: %s",
    CORS_ORIGINS
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
    ],
    allow_headers=[
        "Content-Type",
        "X-Session-Token",
    ],
)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from the environment"
    )

MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

GEMINI_TIMEOUT_MS = int(
    os.getenv(
        "GEMINI_TIMEOUT_MS",
        "30000"
    )
)

client = genai.Client(
    api_key=api_key,
    http_options={
        "timeout": GEMINI_TIMEOUT_MS
    }
)

init_db()

RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv(
        "RATE_LIMIT_WINDOW_SECONDS",
        "60"
    )
)

RATE_LIMIT_MAX_REQUESTS = int(
    os.getenv(
        "RATE_LIMIT_MAX_REQUESTS",
        "10"
    )
)

_request_times: Dict[str, Deque[float]] = defaultdict(
    deque
)


def check_rate_limit(key: str) -> bool:
    now = time.monotonic()
    bucket = _request_times[key]

    while (
        bucket
        and now - bucket[0]
        > RATE_LIMIT_WINDOW_SECONDS
    ):
        bucket.popleft()

    if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    bucket.append(now)

    return True


@app.get("/")
def home():
    return {
        "message": "AI Interview Preparation OS Backend is running!",
        "version": "0.4.0",
        "frontend": "/app/",
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.post("/session/start")
def start_session(data: dict):
    candidate_id = str(
        data.get(
            "candidate_id",
            ""
        )
    ).strip()

    session_id = str(
        data.get(
            "session_id",
            ""
        )
    ).strip()

    access_token = data.get(
        "access_token"
    )

    if (
        not candidate_id
        or len(candidate_id) > 150
    ):
        raise HTTPException(
            status_code=400,
            detail="A valid candidate ID is required."
        )

    if (
        not session_id
        or len(session_id) > 100
    ):
        raise HTTPException(
            status_code=400,
            detail="A valid session ID is required."
        )

    try:
        token, is_new = ensure_candidate_access(
            candidate_id,
            access_token
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail="Candidate access is not authorized."
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc

    session_token = token

    try:
        create_session(
            session_id,
            candidate_id,
            session_token
        )

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Session ID already exists. Start a new interview."
        )

    return {
        "session_id": session_id,
        "candidate_id": candidate_id.strip().lower(),
        "access_token": session_token,
        "new_candidate": is_new,
    }


@app.post(
    "/evaluate",
    response_model=InterviewEvaluation
)
def evaluate_answer(
    request: Request,
    data: AnswerRequest,
    x_session_token: Optional[str] = Header(
        default=None
    ),
):
    client_host = (
        request.client.host
        if request.client
        else "unknown"
    )

    if not check_rate_limit(
        f"evaluate:{client_host}"
    ):
        raise HTTPException(
            status_code=429,
            detail="Too many evaluation requests. Please wait and try again."
        )

    if (
        not x_session_token
        or not data.session_id
        or not data.candidate_id
    ):
        raise HTTPException(
            status_code=401,
            detail="Authenticated interview session required."
        )

    if not authorize_session(
        data.session_id,
        x_session_token,
        data.candidate_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Session access denied."
        )

    if not data.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty."
        )

    if not data.answer.strip():
        raise HTTPException(
            status_code=400,
            detail="Please enter an answer first."
        )

    request_id = str(
        uuid.uuid4()
    )

    started = time.perf_counter()

    try:
        evaluation = evaluate_with_retry(
            client,
            data,
            MODEL_NAME
        )

        latency_ms = round(
            (
                time.perf_counter()
                - started
            ) * 1000
        )

        try:
            save_evaluation(
                data,
                evaluation
            )

        except Exception:
            logger.exception(
                "history_save_failed request_id=%s session_id=%s",
                request_id,
                data.session_id or "anonymous",
            )

        logger.info(
            "request_complete request_id=%s session_id=%s candidate_id=%s latency_ms=%s",
            request_id,
            data.session_id or "anonymous",
            data.candidate_id or "anonymous",
            latency_ms,
        )

        return evaluation

    except Exception as exc:
        latency_ms = round(
            (
                time.perf_counter()
                - started
            ) * 1000
        )

        logger.error(
            "request_failed request_id=%s session_id=%s latency_ms=%s error=%s",
            request_id,
            data.session_id or "anonymous",
            latency_ms,
            exc,
        )

        raise HTTPException(
            status_code=502,
            detail="The AI evaluator is temporarily unavailable. Please try again."
        ) from exc


@app.get(
    "/history/{session_id}"
)
def history(
    session_id: str,
    x_session_token: Optional[str] = Header(
        default=None
    ),
):
    if (
        not x_session_token
        or not authorize_session(
            session_id,
            x_session_token
        )
    ):
        raise HTTPException(
            status_code=403,
            detail="Session access denied."
        )

    return get_session_history(
        session_id
    )


@app.get(
    "/history/candidate/{candidate_id}"
)
def candidate_history(
    candidate_id: str,
    x_session_token: Optional[str] = Header(
        default=None
    ),
):
    if (
        not x_session_token
        or not authorize_candidate(
            candidate_id,
            x_session_token
        )
    ):
        raise HTTPException(
            status_code=403,
            detail="Candidate access denied."
        )

    return get_candidate_history(
        candidate_id
    )


@app.get(
    "/history/candidate/{candidate_id}/summary"
)
def candidate_summary(
    candidate_id: str,
    x_session_token: Optional[str] = Header(
        default=None
    ),
):
    if (
        not x_session_token
        or not authorize_candidate(
            candidate_id,
            x_session_token
        )
    ):
        raise HTTPException(
            status_code=403,
            detail="Candidate access denied."
        )

    return get_candidate_summary(
        candidate_id
    )


FRONTEND_DIR = (
    Path(__file__).resolve().parent.parent
    / "Frontend"
)

if FRONTEND_DIR.exists():
    app.mount(
        "/app",
        StaticFiles(
            directory=FRONTEND_DIR,
            html=True
        ),
        name="frontend"
    )


@app.get("/app")
def redirect_to_frontend():
    return RedirectResponse(
        url="/app/"
    )