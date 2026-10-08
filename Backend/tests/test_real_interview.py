from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from interview_engine import InterviewType
from personalized_interview import PersonalizedInterviewPlan, PersonalizedQuestionPlan
from real_interview import (
    advance_after_answer,
    build_final_report,
    current_question_payload,
    state_from_plan,
)


def _plan():
    return PersonalizedInterviewPlan(
        role="Machine Learning Engineer",
        total_questions=2,
        focus_areas=["Kubernetes", "Python"],
        gap_topics=["Kubernetes"],
        strength_topics=["Python"],
        questions=[
            PersonalizedQuestionPlan(
                priority="high",
                category="gap",
                topic="Kubernetes",
                objective="Test deployment knowledge",
                question="How would you deploy an ML service with Kubernetes?",
                evidence_source="JD required technology missing from resume",
            ),
            PersonalizedQuestionPlan(
                priority="medium",
                category="strength",
                topic="Python",
                objective="Validate Python depth",
                question="Describe a Python project and a technical decision you made.",
                evidence_source="JD required skill matched by resume",
            ),
        ],
    )


def test_state_from_personalized_plan_creates_live_questions():
    state = state_from_plan("live-1", "candidate-1", _plan())
    assert state.config.role == "Machine Learning Engineer"
    assert state.config.interview_type is InterviewType.technical
    assert len(state.questions) == 2
    assert state.current_question.text.startswith("How would you deploy")


def test_current_question_payload_contains_progress():
    state = state_from_plan("live-2", "candidate-2", _plan())
    payload = current_question_payload(state)
    assert payload["question_number"] == 1
    assert payload["total_questions"] == 2
    assert payload["skills"] == ["Kubernetes"]


def test_advance_after_answer_moves_to_next_question():
    state = state_from_plan("live-3", "candidate-3", _plan())
    advance_after_answer(state, state.current_question.id)
    assert state.current_index == 1
    assert state.answered_question_ids == ["personalized-001-kubernetes"]
    assert state.current_question.id == "personalized-002-python"


def test_advance_rejects_stale_question():
    state = state_from_plan("live-4", "candidate-4", _plan())
    try:
        advance_after_answer(state, "wrong-question")
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("Expected stale question rejection")


def test_final_report_empty_session_is_not_completed(monkeypatch):
    monkeypatch.setattr("real_interview.get_live_answers", lambda session_id, candidate_id: [])
    report = build_final_report("live-5", "candidate-5")
    assert report["completed"] is False
    assert report["average_score"] is None


def test_final_report_calculates_score_summary(monkeypatch):
    monkeypatch.setattr(
        "real_interview.get_live_answers",
        lambda session_id, candidate_id: [
            {"score": 80},
            {"score": 60},
        ],
    )
    report = build_final_report("live-6", "candidate-6")
    assert report["completed"] is True
    assert report["questions_answered"] == 2
    assert report["average_score"] == 70
    assert report["highest_score"] == 80
    assert report["lowest_score"] == 60
