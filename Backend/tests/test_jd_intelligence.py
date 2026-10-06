from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient

import main
from jd_parser import JDAnalysis, JDAnalysisResult, InterviewBlueprint


def test_jd_request_rejects_too_short_text():
    client = TestClient(main.app)
    response = client.post("/jd/analyze", json={"jd_text": "too short"})
    assert response.status_code == 422


def test_jd_analysis_requires_gemini_when_not_configured(monkeypatch):
    client = TestClient(main.app)
    monkeypatch.setattr(main, "client", None)
    response = client.post(
        "/jd/analyze",
        json={"jd_text": "Software Engineer role requiring Python and SQL experience."},
    )
    assert response.status_code == 503


def test_jd_analysis_returns_structured_profile(monkeypatch):
    expected = JDAnalysisResult(
        analysis=JDAnalysis(
            role="Machine Learning Engineer",
            seniority="mid-level",
            experience="2+ years",
            required_skills=["Python", "Machine Learning"],
            preferred_skills=["Docker"],
            technologies=["Python", "scikit-learn", "Docker"],
            responsibilities=["Build ML models", "Deploy models"],
            domain=["Machine Learning"],
            education=["B.Tech in Computer Science"],
            soft_skills=["Communication"],
        ),
        blueprint=InterviewBlueprint(
            technical_topics=["Python", "Machine Learning"],
            behavioral_topics=["Communication"],
            system_design_topics=["Model deployment"],
            priority_topics=["Machine Learning", "Python"],
            recommended_interview_types=["technical", "aiml", "hr"],
            recommended_difficulty="medium",
            recommended_question_count=10,
        ),
    )

    monkeypatch.setattr(main, "client", object())
    monkeypatch.setattr(
        main,
        "analyze_job_description",
        lambda client, model_name, jd_text: expected,
    )

    response = TestClient(main.app).post(
        "/jd/analyze",
        json={
            "jd_text": """Machine Learning Engineer\n\n2+ years experience.
            Required: Python, Machine Learning. Preferred: Docker.
            Build and deploy ML models."""
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis"]["role"] == "Machine Learning Engineer"
    assert "Python" in body["analysis"]["required_skills"]
    assert body["blueprint"]["recommended_difficulty"] == "medium"
    assert body["blueprint"]["recommended_question_count"] == 10


def test_jd_driven_interview_start_uses_blueprint(monkeypatch):
    from storage import create_session

    expected = JDAnalysisResult(
        analysis=JDAnalysis(
            role="Machine Learning Engineer",
            seniority="mid-level",
            experience="2+ years",
            required_skills=["Python", "Machine Learning"],
            preferred_skills=["Docker"],
            technologies=["Python", "scikit-learn", "Docker"],
            responsibilities=["Build ML models", "Deploy models"],
            domain=["Machine Learning"],
            education=[],
            soft_skills=["Communication"],
        ),
        blueprint=InterviewBlueprint(
            technical_topics=["Python", "Machine Learning"],
            behavioral_topics=["Communication"],
            system_design_topics=["Model deployment"],
            priority_topics=["Machine Learning", "Python"],
            recommended_interview_types=["aiml", "technical"],
            recommended_difficulty="hard",
            recommended_question_count=2,
        ),
    )

    session_id = "jd-blueprint-session-v2"
    candidate_id = "jd-blueprint-candidate-v2"
    token = create_session(session_id, candidate_id)

    monkeypatch.setattr(main, "client", object())
    monkeypatch.setattr(
        main,
        "analyze_job_description",
        lambda client, model_name, jd_text: expected,
    )

    response = TestClient(main.app).post(
        "/interview/start-from-jd",
        headers={"X-Session-Token": token},
        json={
            "session_id": session_id,
            "candidate_id": candidate_id,
            "jd_text": "Machine Learning Engineer requiring Python, ML and Docker experience.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "Machine Learning Engineer"
    assert body["interview_type"] == "aiml"
    assert body["difficulty"] == "hard"
    assert body["question_count"] == 2
    assert body["question"]["question_number"] == 1


def test_jd_driven_interview_start_requires_authentication():
    response = TestClient(main.app).post(
        "/interview/start-from-jd",
        json={
            "session_id": "jd-auth-session",
            "candidate_id": "jd-auth-candidate",
            "jd_text": "Software Engineer requiring Python and SQL experience.",
        },
    )
    assert response.status_code == 401


def test_jd_driven_interview_start_resumes_existing_state(monkeypatch):
    from storage import create_session

    expected = JDAnalysisResult(
        analysis=JDAnalysis(role="Software Engineer"),
        blueprint=InterviewBlueprint(
            recommended_interview_types=["technical"],
            recommended_difficulty="medium",
            recommended_question_count=2,
        ),
    )

    session_id = "jd-resume-session-v2"
    candidate_id = "jd-resume-candidate-v2"
    token = create_session(session_id, candidate_id)

    monkeypatch.setattr(main, "client", object())
    monkeypatch.setattr(
        main,
        "analyze_job_description",
        lambda client, model_name, jd_text: expected,
    )

    client = TestClient(main.app)
    payload = {
        "session_id": session_id,
        "candidate_id": candidate_id,
        "jd_text": "Software Engineer requiring Python and SQL experience.",
    }
    headers = {"X-Session-Token": token}

    first = client.post("/interview/start-from-jd", headers=headers, json=payload)
    assert first.status_code == 200
    first_id = first.json()["question"]["id"]

    next_response = client.post(
        "/interview/next",
        headers=headers,
        json={
            "session_id": session_id,
            "candidate_id": candidate_id,
            "question_id": first_id,
        },
    )
    assert next_response.status_code == 200
    second_id = next_response.json()["question"]["id"]

    resumed = client.post("/interview/start-from-jd", headers=headers, json=payload)
    assert resumed.status_code == 200
    assert resumed.json()["question"]["id"] == second_id
    assert resumed.json()["question"]["question_number"] == 2
