from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient

import main
from jd_parser import JDAnalysis
from personalized_interview import build_personalized_interview_plan
from resume_parser import ResumeAnalysis, ResumeJDMatch


def _resume():
    return ResumeAnalysis(
        target_role="Machine Learning Engineer",
        skills=["Python", "Machine Learning"],
        technologies=["scikit-learn"],
    )


def _jd():
    return JDAnalysis(
        role="Machine Learning Engineer",
        required_skills=["Python", "Machine Learning", "Kubernetes"],
        technologies=["scikit-learn", "Docker", "Kubernetes"],
        responsibilities=["Deploy and monitor ML models"],
        domain=["Machine Learning"],
    )


def _match():
    return ResumeJDMatch(
        match_score=55,
        matched_required_skills=["Python", "Machine Learning"],
        missing_required_skills=["Kubernetes"],
        matched_technologies=["scikit-learn"],
        missing_technologies=["Docker", "Kubernetes"],
    )


def test_personalized_plan_prioritizes_missing_required_skills():
    plan = build_personalized_interview_plan(_resume(), _jd(), _match(), question_count=5)
    assert plan.total_questions == 5
    assert plan.questions[0].priority == "high"
    assert plan.questions[0].topic == "Kubernetes"
    assert "Kubernetes" in plan.gap_topics


def test_personalized_plan_validates_existing_strengths():
    plan = build_personalized_interview_plan(_resume(), _jd(), _match(), question_count=6)
    topics = [item.topic for item in plan.questions]
    assert "Python" in topics
    assert "Machine Learning" in topics
    assert any(item.category == "strength" for item in plan.questions)


def test_personalized_plan_includes_jd_responsibility():
    plan = build_personalized_interview_plan(_resume(), _jd(), _match(), question_count=10)
    assert any(
        item.category == "responsibility"
        and "Deploy and monitor ML models" in item.topic
        for item in plan.questions
    )


def test_personalized_plan_is_bounded():
    plan = build_personalized_interview_plan(_resume(), _jd(), _match(), question_count=100)
    assert 1 <= plan.total_questions <= 50
    assert len(plan.questions) == plan.total_questions


def test_personalized_plan_has_no_duplicate_topics():
    plan = build_personalized_interview_plan(_resume(), _jd(), _match(), question_count=20)
    topics = [item.topic.casefold() for item in plan.questions]
    assert len(topics) == len(set(topics))


def test_personalized_plan_endpoint_combines_resume_jd_and_match(monkeypatch):
    from jd_parser import JDAnalysisResult, InterviewBlueprint
    from resume_parser import ResumeAnalysisResult

    resume_result = ResumeAnalysisResult(profile=_resume())
    jd_result = JDAnalysisResult(analysis=_jd(), blueprint=InterviewBlueprint(recommended_question_count=6))
    match_result = _match()

    monkeypatch.setattr(main, "client", object())
    monkeypatch.setattr(main, "analyze_resume", lambda client, model_name, resume_text: resume_result)
    monkeypatch.setattr(main, "analyze_job_description", lambda client, model_name, jd_text: jd_result)
    monkeypatch.setattr(main, "match_resume_to_jd", lambda profile, required_skills, preferred_skills, technologies: match_result)

    response = TestClient(main.app).post(
        "/interview/personalized-plan",
        json={
            "resume_text": "Python machine learning engineer with scikit-learn experience.",
            "jd_text": "Machine Learning Engineer requiring Python, Kubernetes and Docker.",
            "question_count": 6,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "Machine Learning Engineer"
    assert body["total_questions"] == 6
    assert body["questions"][0]["priority"] == "high"


def test_personalized_plan_endpoint_requires_gemini(monkeypatch):
    monkeypatch.setattr(main, "client", None)
    response = TestClient(main.app).post(
        "/interview/personalized-plan",
        json={
            "resume_text": "Python machine learning engineer with scikit-learn experience.",
            "jd_text": "Machine Learning Engineer requiring Python and Kubernetes.",
            "question_count": 5,
        },
    )
    assert response.status_code == 503
