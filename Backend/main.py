
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
from jd_parser import JDAnalysisResult, analyze_job_description
from resume_parser import ResumeAnalysisResult, ResumeJDMatch, analyze_resume, match_resume_to_jd
from personalized_interview import PersonalizedInterviewPlan, build_personalized_interview_plan
from adaptive_difficulty import adapt_after_answer
from real_interview import (
    build_final_report,
    get_live_answers,
    current_question_payload,
    init_real_interview_db,
    save_live_answer,
    state_from_plan,
)
from interview_engine import (
    InterviewConfig,
    InterviewEngine,
    InterviewType,
    init_interview_state_db,
    load_interview_state,
    save_interview_state,
)
from models import (
    AnswerRequest,
    InterviewEvaluation,
    InterviewQuestionResponse,
    InterviewStartRequest,
    InterviewStartResponse,
)
from storage import (
    authorize_candidate,
    authorize_session,
    check_database,
    create_session,
    ensure_candidate_access,
    get_candidate_history,
    get_candidate_summary,
    get_evaluation_by_request_id,
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


app = FastAPI(title="AI Interview Preparation OS", version="1.0.0")

cors_origins = [
    x.strip().rstrip("/")
    for x in os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    if x.strip()
]

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

client = (
    genai.Client(
        api_key=api_key,
        http_options={"timeout": GEMINI_TIMEOUT_MS},
    )
    if api_key and api_key not in {"your_gemini_api_key_here", "CHANGE_ME"}
    else None
)

init_db()
init_interview_state_db()
init_real_interview_db()
interview_engine = InterviewEngine()

RATE_LIMIT_WINDOW_SECONDS = _env_int(
    "RATE_LIMIT_WINDOW_SECONDS",
    60,
)
RATE_LIMIT_MAX_REQUESTS = _env_int(
    "RATE_LIMIT_MAX_REQUESTS",
    10,
)

_request_times: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = threading.Lock()


class ResumeAnalyzeRequest(BaseModel):
    resume_text: str = Field(min_length=50, max_length=30000)

    def normalized_text(self) -> str:
        return self.resume_text.strip()


class ResumeAnalyzeResponse(ResumeAnalysisResult):
    pass


class ResumeJDMatchRequest(BaseModel):
    resume_text: str = Field(min_length=50, max_length=30000)
    jd_text: str = Field(min_length=20, max_length=15000)

    def normalized_resume(self) -> str:
        return self.resume_text.strip()

    def normalized_jd(self) -> str:
        return self.jd_text.strip()


class ResumeJDMatchResponse(ResumeJDMatch):
    pass


class JDAnalyzeRequest(BaseModel):
    jd_text: str = Field(min_length=20, max_length=15000)

    def normalized_text(self) -> str:
        return self.jd_text.strip()


class JDAnalyzeResponse(JDAnalysisResult):
    pass




class JDInterviewStartRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=150)
    session_id: str = Field(min_length=1, max_length=100)
    jd_text: str = Field(min_length=20, max_length=15000)

    def normalized_candidate(self) -> str:
        return self.candidate_id.strip()

    def normalized_session(self) -> str:
        return self.session_id.strip()

    def normalized_text(self) -> str:
        return self.jd_text.strip()


class SessionStartRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=150)
    session_id: str = Field(min_length=1, max_length=100)
    access_token: str | None = Field(default=None, max_length=500)

    def normalized_candidate(self) -> str:
        return self.candidate_id.strip()

    def normalized_session(self) -> str:
        return self.session_id.strip()


class InterviewNextRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=150)
    session_id: str = Field(min_length=1, max_length=100)
    question_id: str = Field(min_length=1, max_length=150)

    def normalized_candidate(self) -> str:
        return self.candidate_id.strip()

    def normalized_session(self) -> str:
        return self.session_id.strip()

    def normalized_question(self) -> str:
        return self.question_id.strip()


class InterviewNextResponse(BaseModel):
    session_id: str
    candidate_id: str
    completed: bool
    question: InterviewQuestionResponse | None = None
    question_number: int
    total_questions: int


class LiveInterviewStartRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=150)
    session_id: str = Field(min_length=1, max_length=100)
    plan: PersonalizedInterviewPlan

    def normalized_candidate(self) -> str:
        return self.candidate_id.strip()

    def normalized_session(self) -> str:
        return self.session_id.strip()


class LiveInterviewStartResponse(BaseModel):
    session_id: str
    candidate_id: str
    role: str
    completed: bool
    question: InterviewQuestionResponse | None = None
    question_number: int
    total_questions: int


class LiveInterviewAnswerRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=150)
    session_id: str = Field(min_length=1, max_length=100)
    question_id: str = Field(min_length=1, max_length=150)
    answer: str = Field(min_length=1, max_length=12000)

    def normalized_candidate(self) -> str:
        return self.candidate_id.strip()

    def normalized_session(self) -> str:
        return self.session_id.strip()

    def normalized_question(self) -> str:
        return self.question_id.strip()

    def normalized_answer(self) -> str:
        return self.answer.strip()


class LiveInterviewAnswerResponse(BaseModel):
    session_id: str
    candidate_id: str
    question_id: str
    evaluation: InterviewEvaluation
    completed: bool
    question: InterviewQuestionResponse | None = None
    question_number: int
    total_questions: int
    final_report: dict | None = None


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

        return max(
            1,
            math.ceil(
                RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])
            ),
        )


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
            stale = [
                k
                for k, v in _request_times.items()
                if not v
                or now - v[-1] >= RATE_LIMIT_WINDOW_SECONDS
            ]

            for k in stale[:2000]:
                _request_times.pop(k, None)

        return allowed


def _require_client() -> genai.Client:
    if client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "AI evaluator is not configured. "
                "Set GEMINI_API_KEY and restart the backend."
            ),
        )

    return client


@app.get("/")
def home():
    return {
        "message": "AI Interview Preparation OS Backend is running!",
        "version": app.version,
        "frontend": "/app/",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": app.version,
    }


@app.get("/ready")
def ready():
    checks = {
        "database": check_database(),
        "gemini_configured": client is not None,
    }

    ready_state = all(checks.values())

    if not ready_state:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "checks": checks,
                "version": app.version,
            },
        )

    return {
        "status": "ready",
        "checks": checks,
        "version": app.version,
    }


@app.post(
    "/jd/analyze",
    response_model=JDAnalyzeResponse,
)
def analyze_jd(data: JDAnalyzeRequest):
    if not data.normalized_text():
        raise HTTPException(
            status_code=400,
            detail="Job description is required.",
        )

    try:
        result = analyze_job_description(
            client=_require_client(),
            model_name=MODEL_NAME,
            jd_text=data.normalized_text(),
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("JD analysis failed")
        raise HTTPException(
            status_code=502,
            detail="JD analysis provider failed.",
        ) from exc

    return JDAnalyzeResponse.model_validate(result.model_dump())


@app.post(
    "/resume/analyze",
    response_model=ResumeAnalyzeResponse,
)
def analyze_resume_endpoint(data: ResumeAnalyzeRequest):
    if not data.normalized_text():
        raise HTTPException(status_code=400, detail="Resume is required.")

    try:
        result = analyze_resume(
            client=_require_client(),
            model_name=MODEL_NAME,
            resume_text=data.normalized_text(),
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Resume analysis failed")
        raise HTTPException(status_code=502, detail="Resume analysis provider failed.") from exc

    return ResumeAnalyzeResponse.model_validate(result.model_dump())


@app.post(
    "/resume/match-jd",
    response_model=ResumeJDMatchResponse,
)
def match_resume_to_job_description(data: ResumeJDMatchRequest):
    if not data.normalized_resume() or not data.normalized_jd():
        raise HTTPException(status_code=400, detail="Resume and job description are required.")

    try:
        resume_result = analyze_resume(
            client=_require_client(),
            model_name=MODEL_NAME,
            resume_text=data.normalized_resume(),
        )
        jd_result = analyze_job_description(
            client=_require_client(),
            model_name=MODEL_NAME,
            jd_text=data.normalized_jd(),
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Resume-JD matching failed")
        raise HTTPException(status_code=502, detail="Resume-JD analysis provider failed.") from exc

    match = match_resume_to_jd(
        profile=resume_result.profile,
        required_skills=jd_result.analysis.required_skills,
        preferred_skills=jd_result.analysis.preferred_skills,
        technologies=jd_result.analysis.technologies,
    )
    return ResumeJDMatchResponse.model_validate(match.model_dump())


class PersonalizedInterviewPlanRequest(BaseModel):
    resume_text: str = Field(min_length=50, max_length=30000)
    jd_text: str = Field(min_length=20, max_length=15000)
    question_count: int = Field(default=10, ge=1, le=50)

    def normalized_resume(self) -> str:
        return self.resume_text.strip()

    def normalized_jd(self) -> str:
        return self.jd_text.strip()


@app.post(
    "/interview/personalized-plan",
    response_model=PersonalizedInterviewPlan,
)
def personalized_interview_plan(data: PersonalizedInterviewPlanRequest):
    if not data.normalized_resume() or not data.normalized_jd():
        raise HTTPException(
            status_code=400,
            detail="Resume and job description are required.",
        )

    try:
        resume_result = analyze_resume(
            client=_require_client(),
            model_name=MODEL_NAME,
            resume_text=data.normalized_resume(),
        )
        jd_result = analyze_job_description(
            client=_require_client(),
            model_name=MODEL_NAME,
            jd_text=data.normalized_jd(),
        )
        match = match_resume_to_jd(
            profile=resume_result.profile,
            required_skills=jd_result.analysis.required_skills,
            preferred_skills=jd_result.analysis.preferred_skills,
            technologies=jd_result.analysis.technologies,
        )
        return build_personalized_interview_plan(
            resume=resume_result.profile,
            jd=jd_result.analysis,
            match=match,
            question_count=data.question_count,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Personalized interview planning failed")
        raise HTTPException(
            status_code=502,
            detail="Personalized interview planning provider failed.",
        ) from exc


@app.post(
    "/interview/start-from-jd",
    response_model=InterviewStartResponse,
)
def start_interview_from_jd(
    data: JDInterviewStartRequest,
    x_session_token: str | None = Header(default=None),
):
    if not x_session_token:
        raise HTTPException(
            status_code=401,
            detail="Authenticated interview session required.",
        )

    if not authorize_session(
        data.session_id,
        x_session_token,
        data.candidate_id,
    ):
        raise HTTPException(
            status_code=403,
            detail="Session access denied.",
        )

    existing_state = load_interview_state(
        data.session_id,
        data.candidate_id,
    )

    if existing_state is not None:
        question = existing_state.current_question
        if question is None:
            raise HTTPException(
                status_code=409,
                detail="Interview is already completed. Start a new session.",
            )
        return InterviewStartResponse(
            session_id=existing_state.session_id,
            candidate_id=existing_state.candidate_id,
            role=existing_state.config.role,
            interview_type=existing_state.config.interview_type.value,
            difficulty=existing_state.config.difficulty,
            question_count=len(existing_state.questions),
            question=InterviewQuestionResponse(
                id=question.id,
                question=question.text,
                skills=list(question.skills),
                question_number=existing_state.current_index + 1,
                total_questions=len(existing_state.questions),
            ),
        )

    try:
        result = analyze_job_description(
            client=_require_client(),
            model_name=MODEL_NAME,
            jd_text=data.normalized_text(),
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("JD-driven interview analysis failed")
        raise HTTPException(
            status_code=502,
            detail="JD analysis provider failed.",
        ) from exc

    supported_types = {item.value for item in InterviewType}
    interview_type = next(
        (
            item.strip().lower()
            for item in result.blueprint.recommended_interview_types
            if item.strip().lower() in supported_types
        ),
        InterviewType.technical.value,
    )

    difficulty = result.blueprint.recommended_difficulty.strip().lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    question_count = max(1, min(50, result.blueprint.recommended_question_count))

    try:
        config = InterviewConfig(
            role=result.analysis.role,
            interview_type=InterviewType(interview_type),
            difficulty=difficulty,
            question_count=question_count,
        )
        state = interview_engine.create_session(
            session_id=data.session_id,
            candidate_id=data.candidate_id,
            config=config,
        )
        save_interview_state(state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    question = state.current_question
    if question is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to create interview question.",
        )

    return InterviewStartResponse(
        session_id=state.session_id,
        candidate_id=state.candidate_id,
        role=state.config.role,
        interview_type=state.config.interview_type.value,
        difficulty=state.config.difficulty,
        question_count=len(state.questions),
        question=InterviewQuestionResponse(
            id=question.id,
            question=question.text,
            skills=list(question.skills),
            question_number=1,
            total_questions=len(state.questions),
        ),
    )


@app.post("/session/start")
def start_session(data: SessionStartRequest):
    candidate_id = data.normalized_candidate()
    session_id = data.normalized_session()

    if not candidate_id or not session_id:
        raise HTTPException(
            status_code=400,
            detail="Candidate ID and session ID are required.",
        )

    try:
        candidate_token, is_new = ensure_candidate_access(
            candidate_id,
            data.access_token,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail="Candidate access is not authorized.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    try:
        session_token = create_session(
            session_id,
            candidate_id,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Session ID already exists. Start a new interview.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "session_id": session_id,
        "candidate_id": candidate_id.lower(),
        "candidate_access_token": candidate_token,
        "session_token": session_token,
        "new_candidate": is_new,
    }


@app.post(
    "/interview/start",
    response_model=InterviewStartResponse,
)
def start_interview(
    data: InterviewStartRequest,
    x_session_token: str | None = Header(default=None),
):
    if not x_session_token:
        raise HTTPException(
            status_code=401,
            detail="Authenticated interview session required.",
        )

    if not authorize_session(
        data.session_id,
        x_session_token,
        data.candidate_id,
    ):
        raise HTTPException(
            status_code=403,
            detail="Session access denied.",
        )

    existing_state = load_interview_state(
        data.session_id,
        data.candidate_id,
    )

    if existing_state is not None:
        question = existing_state.current_question

        if question is None:
            raise HTTPException(
                status_code=409,
                detail="Interview is already completed. Start a new session.",
            )

        return InterviewStartResponse(
            session_id=existing_state.session_id,
            candidate_id=existing_state.candidate_id,
            role=existing_state.config.role,
            interview_type=existing_state.config.interview_type.value,
            difficulty=existing_state.config.difficulty,
            question_count=len(existing_state.questions),
            question=InterviewQuestionResponse(
                id=question.id,
                question=question.text,
                skills=list(question.skills),
                question_number=existing_state.current_index + 1,
                total_questions=len(existing_state.questions),
            ),
        )

    try:
        interview_type = InterviewType(
            data.interview_type.lower()
        )

        config = InterviewConfig(
            role=data.role,
            interview_type=interview_type,
            difficulty=data.difficulty.value,
            question_count=data.question_count,
        )

        state = interview_engine.create_session(
            session_id=data.session_id,
            candidate_id=data.candidate_id,
            config=config,
        )
        save_interview_state(state)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    question = state.current_question

    if question is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to create interview question.",
        )

    return InterviewStartResponse(
        session_id=state.session_id,
        candidate_id=state.candidate_id,
        role=state.config.role,
        interview_type=state.config.interview_type.value,
        difficulty=state.config.difficulty,
        question_count=len(state.questions),
        question=InterviewQuestionResponse(
            id=question.id,
            question=question.text,
            skills=list(question.skills),
            question_number=1,
            total_questions=len(state.questions),
        ),
    )


@app.post(
    "/interview/live/start",
    response_model=LiveInterviewStartResponse,
)
def start_live_interview(
    data: LiveInterviewStartRequest,
    x_session_token: str | None = Header(default=None),
):
    candidate_id = data.normalized_candidate()
    session_id = data.normalized_session()

    if not x_session_token:
        raise HTTPException(
            status_code=401,
            detail="Authenticated interview session required.",
        )

    if not authorize_session(session_id, x_session_token, candidate_id):
        raise HTTPException(status_code=403, detail="Session access denied.")

    existing_state = load_interview_state(session_id, candidate_id)
    if existing_state is not None:
        question_payload = current_question_payload(existing_state)
        if question_payload is None:
            raise HTTPException(
                status_code=409,
                detail="Interview is already completed. Start a new session.",
            )
        return LiveInterviewStartResponse(
            session_id=session_id,
            candidate_id=candidate_id,
            role=existing_state.config.role,
            completed=False,
            question=InterviewQuestionResponse(**question_payload),
            question_number=existing_state.current_index + 1,
            total_questions=len(existing_state.questions),
        )

    try:
        state = state_from_plan(session_id, candidate_id, data.plan)
        save_interview_state(state)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    question_payload = current_question_payload(state)
    return LiveInterviewStartResponse(
        session_id=session_id,
        candidate_id=candidate_id,
        role=state.config.role,
        completed=False,
        question=InterviewQuestionResponse(**question_payload),
        question_number=1,
        total_questions=len(state.questions),
    )


def build_recent_live_scores(session_id: str, candidate_id: str) -> list[float]:
    return [float(item["score"]) for item in get_live_answers(session_id, candidate_id)]


@app.post(
    "/interview/live/answer",
    response_model=LiveInterviewAnswerResponse,
)
def submit_live_interview_answer(
    request: Request,
    data: LiveInterviewAnswerRequest,
    x_session_token: str | None = Header(default=None),
    x_evaluation_id: str | None = Header(default=None, alias="X-Evaluation-Id"),
):
    candidate_id = data.normalized_candidate()
    session_id = data.normalized_session()
    question_id = data.normalized_question()

    if not x_session_token:
        raise HTTPException(status_code=401, detail="Authenticated interview session required.")
    if not authorize_session(session_id, x_session_token, candidate_id):
        raise HTTPException(status_code=403, detail="Session access denied.")

    state = load_interview_state(session_id, candidate_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Interview state not found.")

    current = state.current_question
    if current is None:
        raise HTTPException(status_code=409, detail="Interview is already completed.")
    if current.id != question_id:
        raise HTTPException(status_code=409, detail="The answered question does not match the current question.")
    if question_id in state.answered_question_ids:
        raise HTTPException(status_code=409, detail="This question has already been answered.")

    request_id = (x_evaluation_id or str(uuid.uuid4())).strip()
    if len(request_id) > 100:
        raise HTTPException(status_code=400, detail="Evaluation ID is too long.")

    existing = get_evaluation_by_request_id(request_id, session_id, candidate_id)
    if existing is not None:
        evaluation = existing
    else:
        client_host = request.client.host if request.client else "unknown"
        rate_key = f"evaluate:{client_host}"
        if not check_rate_limit(rate_key):
            retry_after = _rate_limit_retry_after(rate_key)
            raise HTTPException(
                status_code=429,
                detail="Too many evaluation requests. Please wait and try again.",
                headers={"Retry-After": str(retry_after)},
            )

        answer_request = AnswerRequest(
            session_id=session_id,
            candidate_id=candidate_id,
            role=state.config.role,
            difficulty=current.difficulty,
            question=current.text,
            answer=data.normalized_answer(),
            expected_skills=list(current.skills),
        )

        try:
            evaluation = evaluate_with_retry(
                _require_client(),
                answer_request,
                MODEL_NAME,
            )
            evaluation, _ = save_evaluation(
                answer_request,
                evaluation,
                request_id,
            )
        except EvaluationValidationError as exc:
            raise HTTPException(
                status_code=502,
                detail="The AI evaluator returned an invalid result. Please try again.",
            ) from exc
        except EvaluationProviderError as exc:
            raise HTTPException(
                status_code=503,
                detail="The AI evaluator is temporarily unavailable. Please try again.",
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("live_interview_answer_failed session_id=%s", session_id)
            raise HTTPException(
                status_code=500,
                detail="Unexpected server error while processing the interview answer.",
            ) from exc

    save_live_answer(
        session_id,
        candidate_id,
        question_id,
        request_id,
        evaluation.score,
    )

    try:
        recent_scores = build_recent_live_scores(session_id, candidate_id)
        adapt_after_answer(state, question_id, recent_scores)
        save_interview_state(state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    next_payload = current_question_payload(state)
    completed = next_payload is None
    final_report = build_final_report(session_id, candidate_id) if completed else None

    return LiveInterviewAnswerResponse(
        session_id=session_id,
        candidate_id=candidate_id,
        question_id=question_id,
        evaluation=evaluation,
        completed=completed,
        question=InterviewQuestionResponse(**next_payload) if next_payload else None,
        question_number=state.current_index if completed else state.current_index + 1,
        total_questions=len(state.questions),
        final_report=final_report,
    )


@app.post(
    "/interview/next",
    response_model=InterviewNextResponse,
)
def next_interview_question(
    data: InterviewNextRequest,
    x_session_token: str | None = Header(default=None),
):
    candidate_id = data.normalized_candidate()
    session_id = data.normalized_session()
    question_id = data.normalized_question()

    if not x_session_token:
        raise HTTPException(
            status_code=401,
            detail="Authenticated interview session required.",
        )

    if not authorize_session(
        session_id,
        x_session_token,
        candidate_id,
    ):
        raise HTTPException(
            status_code=403,
            detail="Session access denied.",
        )

    state = load_interview_state(session_id, candidate_id)

    if state is None:
        raise HTTPException(
            status_code=404,
            detail="Interview state not found.",
        )

    try:
        answered_question = interview_engine.mark_answered(state)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    if answered_question.id != question_id:
        # Do not persist a transition when the client tried to advance
        # using a stale or arbitrary question ID.
        state.current_index -= 1
        state.answered_question_ids.pop()
        raise HTTPException(
            status_code=409,
            detail="The answered question does not match the current question.",
        )

    save_interview_state(state)

    question = state.current_question

    if question is None:
        return InterviewNextResponse(
            session_id=state.session_id,
            candidate_id=state.candidate_id,
            completed=True,
            question=None,
            question_number=state.answered_count,
            total_questions=len(state.questions),
        )

    return InterviewNextResponse(
        session_id=state.session_id,
        candidate_id=state.candidate_id,
        completed=False,
        question=InterviewQuestionResponse(
            id=question.id,
            question=question.text,
            skills=list(question.skills),
            question_number=state.current_index + 1,
            total_questions=len(state.questions),
        ),
        question_number=state.current_index + 1,
        total_questions=len(state.questions),
    )


@app.post(
    "/evaluate",
    response_model=InterviewEvaluation,
)
def evaluate_answer(
    request: Request,
    data: AnswerRequest,
    x_session_token: str | None = Header(default=None),
    x_evaluation_id: str | None = Header(
        default=None,
        alias="X-Evaluation-Id",
    ),
):
    client_host = (
        request.client.host
        if request.client
        else "unknown"
    )

    rate_key = f"evaluate:{client_host}"

    if not x_session_token:
        raise HTTPException(
            status_code=401,
            detail="Authenticated interview session required.",
        )

    if not data.session_id or not data.candidate_id:
        raise HTTPException(
            status_code=400,
            detail="Session ID and candidate ID are required.",
        )

    if not authorize_session(
        data.session_id,
        x_session_token,
        data.candidate_id,
    ):
        raise HTTPException(
            status_code=403,
            detail="Session access denied.",
        )

    if not data.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    if not data.answer.strip():
        raise HTTPException(
            status_code=400,
            detail="Please enter an answer first.",
        )

    if not check_rate_limit(rate_key):
        retry_after = _rate_limit_retry_after(rate_key)

        raise HTTPException(
            status_code=429,
            detail="Too many evaluation requests. Please wait and try again.",
            headers={
                "Retry-After": str(retry_after),
            },
        )

    request_id = (
        x_evaluation_id or str(uuid.uuid4())
    ).strip()

    if len(request_id) > 100:
        raise HTTPException(
            status_code=400,
            detail="Evaluation ID is too long.",
        )

    existing = get_evaluation_by_request_id(
        request_id,
        data.session_id,
        data.candidate_id,
    )

    if existing is not None:
        return existing

    started = time.perf_counter()

    try:
        evaluation = evaluate_with_retry(
            _require_client(),
            data,
            MODEL_NAME,
        )

        latency_ms = round(
            (time.perf_counter() - started) * 1000
        )

        history_saved = True

        try:
            stored_evaluation, _ = save_evaluation(
                data,
                evaluation,
                request_id,
            )
            evaluation = stored_evaluation
        except Exception:
            history_saved = False

            logger.exception(
                "history_save_failed request_id=%s session_id=%s",
                request_id,
                data.session_id,
            )

        logger.info(
            "request_complete request_id=%s session_id=%s latency_ms=%s history_saved=%s",
            request_id,
            data.session_id,
            latency_ms,
            history_saved,
        )

        return evaluation

    except EvaluationValidationError as exc:
        logger.warning(
            "request_invalid_provider_output request_id=%s error=%s",
            request_id,
            exc,
        )

        raise HTTPException(
            status_code=502,
            detail="The AI evaluator returned an invalid result. Please try again.",
        ) from exc

    except EvaluationProviderError as exc:
        logger.warning(
            "request_provider_unavailable request_id=%s error=%s",
            request_id,
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail="The AI evaluator is temporarily unavailable. Please try again.",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "request_unexpected_failure request_id=%s",
            request_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unexpected server error while evaluating the answer.",
        ) from exc


@app.get("/history/{session_id}")
def history(
    session_id: str,
    x_session_token: str | None = Header(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    if not x_session_token or not authorize_session(
        session_id,
        x_session_token,
    ):
        raise HTTPException(
            status_code=403,
            detail="Session access denied.",
        )

    return get_session_history(
        session_id,
        page=page,
        page_size=page_size,
    )


@app.get("/history/candidate/{candidate_id}")
def candidate_history(
    candidate_id: str,
    x_session_token: str | None = Header(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    if not x_session_token or not authorize_candidate(
        candidate_id,
        x_session_token,
    ):
        raise HTTPException(
            status_code=403,
            detail="Candidate access denied.",
        )

    return get_candidate_history(
        candidate_id,
        page=page,
        page_size=page_size,
    )


@app.get("/history/candidate/{candidate_id}/summary")
def candidate_summary(
    candidate_id: str,
    x_session_token: str | None = Header(default=None),
):
    if not x_session_token or not authorize_candidate(
        candidate_id,
        x_session_token,
    ):
        raise HTTPException(
            status_code=403,
            detail="Candidate access denied.",
        )

    return get_candidate_summary(candidate_id)


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "Frontend"

if FRONTEND_DIR.exists():
    app.mount(
        "/app",
        StaticFiles(
            directory=FRONTEND_DIR,
            html=True,
        ),
        name="frontend",
    )


