import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB = Path(os.environ.get("TEST_DB_PATH", "/tmp/ai_interview_test.db"))
try:
    TEST_DB.unlink()
except FileNotFoundError:
    pass
for suffix in ("-wal", "-shm"):
    try:
        Path(str(TEST_DB) + suffix).unlink()
    except FileNotFoundError:
        pass

os.environ["INTERVIEW_DB_PATH"] = str(TEST_DB)
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["GEMINI_MODEL"] = "test-model"

fake_google = types.ModuleType("google")
fake_genai = types.ModuleType("google.genai")

class FakeClient:
    def __init__(self, *args, **kwargs):
        self.models = types.SimpleNamespace(generate_content=self.generate_content)
        self.response = None
        self.error = None

    def generate_content(self, **kwargs):
        if self.error:
            raise self.error
        return self.response

fake_genai.Client = FakeClient
fake_google.genai = fake_genai
sys.modules["google"] = fake_google
sys.modules["google.genai"] = fake_genai

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import AnswerRequest, Difficulty, InterviewEvaluation
from security import verify_token
import storage
import main

client = TestClient(main.app)


def evaluation_payload(score=80, confidence=0.9):
    return {
        "score": score,
        "technical_accuracy": 8,
        "relevance": 8,
        "clarity": 8,
        "completeness": 8,
        "strengths": ["Clear explanation"],
        "weaknesses": ["Could add an example"],
        "evidence": ["The answer explains the main concept."],
        "feedback": "Good answer.",
        "improved_answer": "A more complete answer.",
        "skills_assessed": [{"skill": "Python", "score": 8}],
        "confidence": confidence,
        "needs_human_review": False,
    }


def start(candidate="tester"):
    response = client.post("/session/start", json={"candidate_id": candidate, "session_id": os.urandom(8).hex()})
    assert response.status_code == 200
    return response.json()


def test_health_and_readiness():
    assert client.get("/health").status_code == 200
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_candidate_and_session_tokens_are_different():
    payload = start("alpha")
    assert payload["candidate_access_token"] != payload["session_token"]


def test_candidate_switch_requires_correct_token():
    first = start("alice")
    second = start("bob")
    denied = client.post("/session/start", json={"candidate_id": "bob", "session_id": os.urandom(8).hex(), "access_token": first["candidate_access_token"]})
    assert denied.status_code == 403
    allowed = client.post("/session/start", json={"candidate_id": "bob", "session_id": os.urandom(8).hex(), "access_token": second["candidate_access_token"]})
    assert allowed.status_code == 200


def test_malformed_access_token_is_validation_error_not_500():
    response = client.post("/session/start", json={"candidate_id": "alice", "session_id": os.urandom(8).hex(), "access_token": 123})
    assert response.status_code == 422


def test_expired_session_is_rejected():
    payload = start("expiry")
    with storage._connect() as conn:
        conn.execute("UPDATE sessions SET expires_at = ? WHERE session_id = ?", ((datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), payload["session_id"]))
    body = {"session_id": payload["session_id"], "candidate_id": "expiry", "question": "What is Python?", "answer": "Python is a programming language.", "difficulty": "easy"}
    response = client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"]})
    assert response.status_code == 403


def test_corrupt_expiry_is_rejected():
    payload = start("corrupt")
    with storage._connect() as conn:
        conn.execute("UPDATE sessions SET expires_at = ? WHERE session_id = ?", ("not-a-date", payload["session_id"]))
    assert not storage.authorize_session(payload["session_id"], payload["session_token"], "corrupt")


def test_invalid_difficulty_rejected():
    payload = start("difficulty")
    body = {"session_id": payload["session_id"], "candidate_id": "difficulty", "question": "What is Python?", "answer": "A language.", "difficulty": "impossible"}
    response = client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"]})
    assert response.status_code == 422


def test_oversized_skill_rejected():
    payload = start("skills")
    body = {"session_id": payload["session_id"], "candidate_id": "skills", "question": "What is Python?", "answer": "A language.", "difficulty": "easy", "expected_skills": ["x" * 101]}
    response = client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"]})
    assert response.status_code == 422


def test_evaluation_provider_and_validation_paths():
    fake = main.client
    fake.response = types.SimpleNamespace(parsed=InterviewEvaluation.model_validate(evaluation_payload()))
    payload = start("eval")
    body = {"session_id": payload["session_id"], "candidate_id": "eval", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
    response = client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"]})
    assert response.status_code == 200
    assert response.json()["score"] == 80


def test_invalid_provider_output_returns_502():
    fake = main.client
    fake.response = types.SimpleNamespace(parsed={"score": 999})
    payload = start("bad-output")
    body = {"session_id": payload["session_id"], "candidate_id": "bad-output", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
    response = client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"]})
    assert response.status_code == 502


def test_provider_failure_returns_503():
    fake = main.client
    fake.error = RuntimeError("provider unavailable")
    payload = start("provider")
    body = {"session_id": payload["session_id"], "candidate_id": "provider", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
    response = client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"]})
    fake.error = None
    assert response.status_code == 503


def test_history_pagination():
    payload = start("history")
    fake = main.client
    fake.response = types.SimpleNamespace(parsed=InterviewEvaluation.model_validate(evaluation_payload()))
    for _ in range(3):
        body = {"session_id": payload["session_id"], "candidate_id": "history", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
        assert client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"]}).status_code == 200
    response = client.get(f"/history/{payload['session_id']}?page=1&page_size=2", headers={"X-Session-Token": payload["session_token"]})
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["has_more"] is True


def test_candidate_summary_still_works():
    payload = start("summary")
    fake = main.client
    fake.response = types.SimpleNamespace(parsed=InterviewEvaluation.model_validate(evaluation_payload()))
    body = {"session_id": payload["session_id"], "candidate_id": "summary", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
    assert client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"]}).status_code == 200
    response = client.get("/history/candidate/summary/summary", headers={"X-Session-Token": payload["candidate_access_token"]})
    assert response.status_code == 200
    assert response.json()["total_answers"] >= 1


def test_rate_limit_returns_429_and_can_expire():
    original_max = main.RATE_LIMIT_MAX_REQUESTS
    main.RATE_LIMIT_MAX_REQUESTS = 2
    main._request_times.clear()
    assert main.check_rate_limit("test-ip") is True
    assert main.check_rate_limit("test-ip") is True
    assert main.check_rate_limit("test-ip") is False
    main.RATE_LIMIT_MAX_REQUESTS = original_max
    main._request_times.clear()


def test_duplicate_session_id_returns_409():
    session_id = os.urandom(8).hex()
    first = client.post("/session/start", json={"candidate_id": "dup", "session_id": session_id})
    second = client.post("/session/start", json={"candidate_id": "dup", "session_id": session_id, "access_token": first.json()["candidate_access_token"]})
    assert first.status_code == 200
    assert second.status_code == 409


def test_safety_heuristics_cover_french_garbled_and_short_technical_off_topic():
    from evaluator import _language_mismatch, _looks_garbled, _likely_off_topic
    assert _language_mismatch("What is an API?", "Une API est une interface qui permet a deux logiciels de communiquer entre eux.") is True
    assert _looks_garbled("Var(X) = E(X^2) - [E(X)]^2 bias hi variance low ... underfit? overfit?? idk") is True
    assert _looks_garbled("asdf qwer zxcv !!!!!!!!") is True
    assert _likely_off_topic("Explain REST API.", "I like pizza and going for long walks on weekends.", "Backend Developer") is True
    assert _likely_off_topic("Tell me about yourself.", "I am a computer science student with internship experience.", "HR") is False


def test_evaluation_idempotency_returns_same_saved_result():
    fake = main.client
    fake.response = types.SimpleNamespace(parsed=InterviewEvaluation.model_validate(evaluation_payload(score=82)))
    payload = start("idempotent")
    body = {"session_id": payload["session_id"], "candidate_id": "idempotent", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
    evaluation_id = "fixed-evaluation-id"
    first = client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"], "X-Evaluation-Id": evaluation_id})
    assert first.status_code == 200
    fake.response = types.SimpleNamespace(parsed=InterviewEvaluation.model_validate(evaluation_payload(score=20)))
    second = client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"], "X-Evaluation-Id": evaluation_id})
    assert second.status_code == 200
    assert second.json()["score"] == 82
    history = client.get(f"/history/{payload['session_id']}", headers={"X-Session-Token": payload["session_token"]}).json()
    assert history["total"] == 1


def test_retry_after_header_is_present():
    original_max = main.RATE_LIMIT_MAX_REQUESTS
    main.RATE_LIMIT_MAX_REQUESTS = 1
    main._request_times.clear()
    payload = start("retry-header")
    fake = main.client
    fake.response = types.SimpleNamespace(parsed=InterviewEvaluation.model_validate(evaluation_payload()))
    body = {"session_id": payload["session_id"], "candidate_id": "retry-header", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
    headers = {"X-Session-Token": payload["session_token"]}
    assert client.post("/evaluate", json=body, headers=headers).status_code == 200
    second = client.post("/evaluate", json=body, headers=headers)
    assert second.status_code == 429
    assert second.headers.get("Retry-After")
    main.RATE_LIMIT_MAX_REQUESTS = original_max
    main._request_times.clear()


def test_candidate_summary_uses_session_creation_time():
    fake = main.client
    fake.response = types.SimpleNamespace(parsed=InterviewEvaluation.model_validate(evaluation_payload()))
    payload = start("started-at")
    session_created = "2020-01-01T00:00:00+00:00"
    with storage._connect() as conn:
        conn.execute("UPDATE sessions SET created_at = ? WHERE session_id = ?", (session_created, payload["session_id"]))
    body = {"session_id": payload["session_id"], "candidate_id": "started-at", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
    assert client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"]}).status_code == 200
    summary = client.get("/history/candidate/started-at/summary", headers={"X-Session-Token": payload["candidate_access_token"]}).json()
    assert summary["sessions"][0]["started_at"] == session_created


def test_history_preserves_complete_evaluation():
    fake = main.client
    payload = start("complete-history")
    evaluation = InterviewEvaluation.model_validate({
        **evaluation_payload(),
        "strengths": ["Precise"],
        "weaknesses": ["Add an example"],
        "evidence": ["The answer defines the concept."],
        "feedback": "Keep the explanation concise.",
        "improved_answer": "A stronger answer includes an example.",
        "skills_assessed": [{"skill": "Python", "score": 9}],
    })
    fake.response = types.SimpleNamespace(parsed=evaluation)
    body = {"session_id": payload["session_id"], "candidate_id": "complete-history", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
    assert client.post("/evaluate", json=body, headers={"X-Session-Token": payload["session_token"]}).status_code == 200
    item = client.get(f"/history/{payload['session_id']}", headers={"X-Session-Token": payload["session_token"]}).json()["items"][0]
    assert item["evaluation"]["feedback"] == evaluation.feedback
    assert item["evaluation"]["strengths"] == ["Precise"]
    assert item["evaluation"]["skills_assessed"][0]["score"] == 9


def test_idempotency_key_is_scoped_to_session_and_candidate():
    fake = main.client
    fake.response = types.SimpleNamespace(parsed=InterviewEvaluation.model_validate(evaluation_payload(score=91)))
    first = start("scope-a")
    second = start("scope-b")
    request_id = "same-id-different-session"
    body_a = {"session_id": first["session_id"], "candidate_id": "scope-a", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
    body_b = {"session_id": second["session_id"], "candidate_id": "scope-b", "question": "Explain Python variables", "answer": "Python variables store references to objects.", "difficulty": "easy"}
    a = client.post("/evaluate", json=body_a, headers={"X-Session-Token": first["session_token"], "X-Evaluation-Id": request_id})
    assert a.status_code == 200
    fake.response = types.SimpleNamespace(parsed=InterviewEvaluation.model_validate(evaluation_payload(score=42)))
    b = client.post("/evaluate", json=body_b, headers={"X-Session-Token": second["session_token"], "X-Evaluation-Id": request_id})
    assert b.status_code == 200
    assert b.json()["score"] == 42


def test_ready_reports_database_failure(monkeypatch):
    monkeypatch.setattr(main, "check_database", lambda: False)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["checks"]["database"] is False
