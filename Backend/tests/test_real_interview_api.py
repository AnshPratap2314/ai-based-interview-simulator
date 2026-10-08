from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient

import main
from models import InterviewEvaluation
from personalized_interview import PersonalizedInterviewPlan, PersonalizedQuestionPlan
from real_interview import state_from_plan


def _plan(count=2):
    questions = [
        PersonalizedQuestionPlan(
            priority="high",
            category="gap",
            topic="Kubernetes",
            objective="Test deployment knowledge",
            question="How would you deploy an ML service with Kubernetes?",
            evidence_source="JD gap",
        )
    ]
    if count == 2:
        questions.append(
            PersonalizedQuestionPlan(
                priority="medium",
                category="strength",
                topic="Python",
                objective="Validate Python depth",
                question="Describe a Python project and a technical decision you made.",
                evidence_source="Resume match",
            )
        )
    return PersonalizedInterviewPlan(
        role="Machine Learning Engineer",
        total_questions=len(questions),
        focus_areas=[item.topic for item in questions],
        gap_topics=["Kubernetes"],
        strength_topics=["Python"],
        questions=questions,
    )


def _evaluation(score=80):
    return InterviewEvaluation(
        score=score,
        technical_accuracy=8,
        relevance=8,
        clarity=8,
        completeness=8,
        strengths=["Clear explanation"],
        weaknesses=["Deployment depth"],
        evidence=["Explained the approach"],
        feedback="Good answer.",
        improved_answer="A stronger answer would include monitoring.",
        skills_assessed=[],
        confidence=0.9,
        needs_human_review=False,
    )


def _auth(monkeypatch):
    monkeypatch.setattr(main, "authorize_session", lambda *args: True)
    monkeypatch.setattr(main, "client", object())


def test_live_start_requires_authentication():
    response = TestClient(main.app).post(
        "/interview/live/start",
        json={"candidate_id": "c1", "session_id": "s1", "plan": _plan().model_dump()},
    )
    assert response.status_code == 401


def test_live_start_returns_first_personalized_question(monkeypatch):
    _auth(monkeypatch)
    saved = {}
    monkeypatch.setattr(main, "load_interview_state", lambda *args: None)
    monkeypatch.setattr(main, "save_interview_state", lambda state: saved.setdefault("state", state))

    response = TestClient(main.app).post(
        "/interview/live/start",
        headers={"X-Session-Token": "token"},
        json={"candidate_id": "c2", "session_id": "s2", "plan": _plan().model_dump()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "Machine Learning Engineer"
    assert body["question"]["skills"] == ["Kubernetes"]
    assert saved["state"].current_index == 0


def test_live_start_resumes_existing_state(monkeypatch):
    _auth(monkeypatch)
    state = state_from_plan("s3", "c3", _plan())
    monkeypatch.setattr(main, "load_interview_state", lambda *args: state)

    response = TestClient(main.app).post(
        "/interview/live/start",
        headers={"X-Session-Token": "token"},
        json={"candidate_id": "c3", "session_id": "s3", "plan": _plan().model_dump()},
    )
    assert response.status_code == 200
    assert response.json()["question"]["id"] == state.questions[0].id


def test_live_answer_evaluates_and_advances(monkeypatch):
    _auth(monkeypatch)
    state = state_from_plan("s4", "c4", _plan())
    saved = []
    monkeypatch.setattr(main, "load_interview_state", lambda *args: state)
    monkeypatch.setattr(main, "save_interview_state", lambda value: saved.append(value))
    monkeypatch.setattr(main, "get_evaluation_by_request_id", lambda *args: None)
    monkeypatch.setattr(main, "evaluate_with_retry", lambda *args: _evaluation(82))
    monkeypatch.setattr(main, "save_evaluation", lambda *args: (_evaluation(82), True))
    monkeypatch.setattr(main, "save_live_answer", lambda *args: None)

    response = TestClient(main.app).post(
        "/interview/live/answer",
        headers={"X-Session-Token": "token", "X-Evaluation-Id": "eval-1"},
        json={
            "candidate_id": "c4",
            "session_id": "s4",
            "question_id": state.questions[0].id,
            "answer": "I would deploy the service with a Kubernetes deployment and service.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evaluation"]["score"] == 82
    assert body["completed"] is False
    assert body["question"]["skills"] == ["Python"]
    assert state.current_index == 1
    assert saved


def test_live_answer_rejects_stale_question(monkeypatch):
    _auth(monkeypatch)
    state = state_from_plan("s5", "c5", _plan())
    monkeypatch.setattr(main, "load_interview_state", lambda *args: state)

    response = TestClient(main.app).post(
        "/interview/live/answer",
        headers={"X-Session-Token": "token"},
        json={
            "candidate_id": "c5",
            "session_id": "s5",
            "question_id": "wrong-question",
            "answer": "answer",
        },
    )
    assert response.status_code == 409


def test_live_answer_returns_final_report(monkeypatch):
    _auth(monkeypatch)
    state = state_from_plan("s6", "c6", _plan(count=1))
    monkeypatch.setattr(main, "load_interview_state", lambda *args: state)
    monkeypatch.setattr(main, "save_interview_state", lambda value: None)
    monkeypatch.setattr(main, "get_evaluation_by_request_id", lambda *args: None)
    monkeypatch.setattr(main, "evaluate_with_retry", lambda *args: _evaluation(90))
    monkeypatch.setattr(main, "save_evaluation", lambda *args: (_evaluation(90), True))
    monkeypatch.setattr(main, "save_live_answer", lambda *args: None)
    monkeypatch.setattr(
        main,
        "build_final_report",
        lambda *args: {"completed": True, "questions_answered": 1, "average_score": 90, "highest_score": 90, "lowest_score": 90},
    )

    response = TestClient(main.app).post(
        "/interview/live/answer",
        headers={"X-Session-Token": "token"},
        json={
            "candidate_id": "c6",
            "session_id": "s6",
            "question_id": state.questions[0].id,
            "answer": "A complete deployment answer.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["completed"] is True
    assert body["question"] is None
    assert body["final_report"]["average_score"] == 90
