import logging
import os
import math
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
from pydantic import BaseModel, Field

from errors import EvaluationProviderError, EvaluationValidationError
from evaluator import evaluate_with_retry
from models import AnswerRequest, InterviewEvaluation
from storage import (
    authorize_candidate,
    check_database,
    get_evaluation_by_request_id,
    authorize_session,
    create_session,
    ensure_candidate_access,
    get_candidate_history,
    get_candidate_summary,
    get_session_history,
    init_db,
    save_evaluation,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


app = FastAPI(title="AI Interview Preparation OS", version="0.6.0")

cors_origins = [x.strip().rstrip("/") for x in os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Session-Token", "X-Evaluation-Id"],
)

api_key = os.getenv("GEMINI_API_KEY", "").strip()
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
GEMINI_TIMEOUT_MS = _env_int("GEMINI_TIMEOUT_MS", 30000, 1000)
client = genai.Client(api_key=api_key, http_options={"timeout": GEMINI_TIMEOUT_MS}) if api_key and api_key not in {"your_gemini_api_key_here", "CHANGE_ME"} else None

init_db()
RATE_LIMIT_WINDOW_SECONDS = _env_int("RATE_LIMIT_WINDOW_SECONDS", 60)
RATE_LIMIT_MAX_REQUESTS = _env_int("RATE_LIMIT_MAX_REQUESTS", 10)
_request_times: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = threading.Lock()


class SessionStartRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=150)
    session_id: str = Field(min_length=1, max_length=100)
    access_token: str | None = Field(default=None, max_length=500)

    def normalized_candidate(self) -> str:
        return self.candidate_id.strip()

    def normalized_session(self) -> str:
        return self.session_id.strip()


def _rate_limit_retry_after(key: str) -> int:
    now = time.monotonic()
    with _rate_limit_lock:
        bucket = _request_times.get(key)
        if not bucket:
            return 1
        while bucket and now - bucket[0] >= RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if not bucket:
            _request_times.pop(key, None)
            return 1
        return max(1, math.ceil(RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])))


def check_rate_limit(key: str) -> bool:
    now = time.monotonic()
    with _rate_limit_lock:
        bucket = _request_times[key]
        while bucket and now - bucket[0] >= RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        allowed = len(bucket) < RATE_LIMIT_MAX_REQUESTS
        if allowed:
            bucket.append(now)
        if not bucket:
            _request_times.pop(key, None)
        if len(_request_times) > 10000:
            stale = [k for k, v in _request_times.items() if not v or now - v[-1] >= RATE_LIMIT_WINDOW_SECONDS]
            for k in stale[:2000]:
                _request_times.pop(k, None)
        return allowed


def _require_client() -> genai.Client:
    if client is None:
        raise HTTPException(status_code=503, detail="AI evaluator is not configured. Set GEMINI_API_KEY and restart the backend.")
    return client


@app.get("/")
def home():
    return {"message": "AI Interview Preparation OS Backend is running!", "version": app.version, "frontend": "/app/"}


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/ready")
def ready():
    checks = {"database": check_database(), "gemini_configured": client is not None}
    ready_state = all(checks.values())
    if not ready_state:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"status": "not_ready", "checks": checks, "version": app.version})
    return {"status": "ready", "checks": checks, "version": app.version}


@app.post("/session/start")
def start_session(data: SessionStartRequest):
    candidate_id = data.normalized_candidate()
    session_id = data.normalized_session()
    if not candidate_id or not session_id:
        raise HTTPException(status_code=400, detail="Candidate ID and session ID are required.")
    try:
        candidate_token, is_new = ensure_candidate_access(candidate_id, data.access_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Candidate access is not authorized.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        session_token = create_session(session_id, candidate_id)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Session ID already exists. Start a new interview.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "session_id": session_id,
        "candidate_id": candidate_id.lower(),
        "candidate_access_token": candidate_token,
        "session_token": session_token,
        "new_candidate": is_new,
    }


@app.post("/evaluate", response_model=InterviewEvaluation)
def evaluate_answer(request: Request, data: AnswerRequest, x_session_token: str | None = Header(default=None), x_evaluation_id: str | None = Header(default=None, alias="X-Evaluation-Id")):
    client_host = request.client.host if request.client else "unknown"
    rate_key = f"evaluate:{client_host}"
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Authenticated interview session required.")
    if not data.session_id or not data.candidate_id:
        raise HTTPException(status_code=400, detail="Session ID and candidate ID are required.")
    if not authorize_session(data.session_id, x_session_token, data.candidate_id):
        raise HTTPException(status_code=403, detail="Session access denied.")
    if not data.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    if not data.answer.strip():
        raise HTTPException(status_code=400, detail="Please enter an answer first.")

    if not check_rate_limit(rate_key):
        retry_after = _rate_limit_retry_after(rate_key)
        raise HTTPException(status_code=429, detail="Too many evaluation requests. Please wait and try again.", headers={"Retry-After": str(retry_after)})

    request_id = (x_evaluation_id or str(uuid.uuid4())).strip()
    if len(request_id) > 100:
        raise HTTPException(status_code=400, detail="Evaluation ID is too long.")
    existing = get_evaluation_by_request_id(request_id, data.session_id, data.candidate_id)
    if existing is not None:
        return existing
    started = time.perf_counter()
    try:
        evaluation = evaluate_with_retry(_require_client(), data, MODEL_NAME)
        latency_ms = round((time.perf_counter() - started) * 1000)
        history_saved = True
        try:
            stored_evaluation, _ = save_evaluation(data, evaluation, request_id)
            evaluation = stored_evaluation
        except Exception:
            history_saved = False
            logger.exception("history_save_failed request_id=%s session_id=%s", request_id, data.session_id)
        logger.info("request_complete request_id=%s session_id=%s latency_ms=%s history_saved=%s", request_id, data.session_id, latency_ms, history_saved)
        return evaluation
    except EvaluationValidationError as exc:
        logger.warning("request_invalid_provider_output request_id=%s error=%s", request_id, exc)
        raise HTTPException(status_code=502, detail="The AI evaluator returned an invalid result. Please try again.") from exc
    except EvaluationProviderError as exc:
        logger.warning("request_provider_unavailable request_id=%s error=%s", request_id, exc)
        raise HTTPException(status_code=503, detail="The AI evaluator is temporarily unavailable. Please try again.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("request_unexpected_failure request_id=%s", request_id)
        raise HTTPException(status_code=500, detail="Unexpected server error while evaluating the answer.") from exc


@app.get("/history/{session_id}")
def history(
    session_id: str,
    x_session_token: str | None = Header(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    if not x_session_token or not authorize_session(session_id, x_session_token):
        raise HTTPException(status_code=403, detail="Session access denied.")
    return get_session_history(session_id, page=page, page_size=page_size)


@app.get("/history/candidate/{candidate_id}")
def candidate_history(
    candidate_id: str,
    x_session_token: str | None = Header(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    if not x_session_token or not authorize_candidate(candidate_id, x_session_token):
        raise HTTPException(status_code=403, detail="Candidate access denied.")
    return get_candidate_history(candidate_id, page=page, page_size=page_size)


@app.get("/history/candidate/{candidate_id}/summary")
def candidate_summary(candidate_id: str, x_session_token: str | None = Header(default=None)):
    if not x_session_token or not authorize_candidate(candidate_id, x_session_token):
        raise HTTPException(status_code=403, detail="Candidate access denied.")
    return get_candidate_summary(candidate_id)


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "Frontend"
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
