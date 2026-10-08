from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient

import main
from models import InterviewEvaluation
from personalized_interview import (
    PersonalizedInterviewPlan,
    PersonalizedQuestionPlan,
)
from real_interview import state_from_plan


def _plan():
    return PersonalizedInterviewPlan(
        role="Machine Learning Engineer",
        total_questions=3,
        focus_areas=["Python", "Kubernetes", "ML"],
        gap_topics=["Kubernetes"],
        strength_topics=["Python"],
        questions=[
            PersonalizedQuestionPlan(
                priority="high",
                category="gap",
                topic="Kubernetes",
                objective="Test Kubernetes",
                question="How would you deploy an ML service with Kubernetes?",
                evidence_source="JD gap",
            ),
            PersonalizedQuestionPlan(
                priority="medium",
                category="strength",
                topic="Python",
                objective="Test Python",
                question="Describe a Python project.",
                evidence_source="Resume match",
            ),
            PersonalizedQuestionPlan(
                priority="high",
                category="gap",
                topic="Machine Learning",
                objective="Test ML depth",
                question="How would you validate an ML model?",
                evidence_source="JD gap",
            ),
        ],
    )


def _evaluation(score):
    return InterviewEvaluation(
        score=score,
        technical_accuracy=8,
        relevance=8,
        clarity=8,
        completeness=8,
        strengths=["Clear"],
        weaknesses=["Could add detail"],
        evidence=["Explained approach"],
        feedback="Good.",
        improved_answer="Add more detail.",
        skills_assessed=[],
        confidence=0.9,
        needs_human_review=False,
    )


def test_live_answer_uses_adaptive_transition(monkeypatch):
    monkeypatch.setattr(main, "authorize_session", lambda *args: True)
    monkeypatch.setattr(main, "client", object())

    state = state_from_plan(
        "adaptive-s1",
        "adaptive-c1",
        _plan(),
    )

    monkeypatch.setattr(
        main,
        "load_interview_state",
        lambda *args: state,
    )
    monkeypatch.setattr(
        main,
        "save_interview_state",
        lambda value: None,
    )
    monkeypatch.setattr(
        main,
        "get_evaluation_by_request_id",
        lambda *args: None,
    )
    monkeypatch.setattr(
        main,
        "evaluate_with_retry",
        lambda *args: _evaluation(95),
    )
    monkeypatch.setattr(
        main,
        "save_evaluation",
        lambda *args: (_evaluation(95), True),
    )
    monkeypatch.setattr(
        main,
        "save_live_answer",
        lambda *args: None,
    )
    monkeypatch.setattr(
        main,
        "get_live_answers",
        lambda *args: [{"score": 95}],
    )

    response = TestClient(main.app).post(
        "/interview/live/answer",
        headers={
            "X-Session-Token": "token",
            "X-Evaluation-Id": "adaptive-eval-1",
        },
        json={
            "candidate_id": "adaptive-c1",
            "session_id": "adaptive-s1",
            "question_id": state.questions[0].id,
            "answer": "A strong answer.",
        },
    )

    assert response.status_code == 200
    assert response.json()["question"]["skills"] == ["Machine Learning"]
    assert state.current_index == 1