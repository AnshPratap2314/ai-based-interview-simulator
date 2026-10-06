from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient

import main
from resume_parser import (
    ResumeAnalysis,
    ResumeAnalysisResult,
    ResumeEducation,
    ResumeProject,
    match_resume_to_jd,
)


def test_resume_request_rejects_too_short_text():
    response = TestClient(main.app).post(
        "/resume/analyze",
        json={"resume_text": "too short"},
    )
    assert response.status_code == 422


def test_resume_analysis_requires_gemini_when_not_configured(monkeypatch):
    monkeypatch.setattr(main, "client", None)
    response = TestClient(main.app).post(
        "/resume/analyze",
        json={"resume_text": "Python developer with machine learning and SQL project experience."},
    )
    assert response.status_code == 503


def test_resume_analysis_returns_structured_profile(monkeypatch):
    expected = ResumeAnalysisResult(
        profile=ResumeAnalysis(
            full_name="Ansh Pratap",
            target_role="Machine Learning Engineer",
            skills=["Python", "Machine Learning", "SQL"],
            technologies=["Python", "scikit-learn", "Docker"],
            programming_languages=["Python", "C++"],
            frameworks_libraries=["scikit-learn"],
            databases=["MySQL"],
            tools=["Git", "Docker"],
            projects=[
                ResumeProject(
                    name="ML Project",
                    description="Built a classification model.",
                    technologies=["Python", "scikit-learn"],
                    skills=["Machine Learning"],
                    outcomes=["Evaluated on a held-out test set"],
                )
            ],
            education=[ResumeEducation(degree="B.Tech", institution="Mewar University", field="CSE")],
            strengths=["Python and ML evidence"],
            gaps=["Limited production ML evidence"],
            evidence=["ML project with scikit-learn"],
        )
    )
    monkeypatch.setattr(main, "client", object())
    monkeypatch.setattr(main, "analyze_resume", lambda client, model_name, resume_text: expected)

    response = TestClient(main.app).post(
        "/resume/analyze",
        json={"resume_text": "Ansh Pratap\nPython ML developer with scikit-learn and MySQL experience."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["target_role"] == "Machine Learning Engineer"
    assert "Python" in body["profile"]["skills"]
    assert body["profile"]["projects"][0]["name"] == "ML Project"


def test_resume_jd_match_is_deterministic():
    profile = ResumeAnalysis(
        skills=["Python", "Machine Learning", "SQL"],
        technologies=["scikit-learn", "Docker"],
        projects=[
            ResumeProject(
                name="ML Platform",
                technologies=["Python", "scikit-learn", "Docker"],
                skills=["Machine Learning"],
            )
        ],
    )
    result = match_resume_to_jd(
        profile,
        required_skills=["Python", "Machine Learning", "Kubernetes"],
        preferred_skills=["SQL"],
        technologies=["Docker", "Kubernetes"],
    )

    assert result.match_score == 72
    assert result.matched_required_skills == ["Python", "Machine Learning"]
    assert result.missing_required_skills == ["Kubernetes"]
    assert result.matched_preferred_skills == ["SQL"]
    assert result.missing_technologies == ["Kubernetes"]
    assert result.relevant_projects == ["ML Platform"]


def test_resume_jd_endpoint_combines_resume_and_jd_analysis(monkeypatch):
    from jd_parser import JDAnalysis, JDAnalysisResult, InterviewBlueprint

    resume_result = ResumeAnalysisResult(
        profile=ResumeAnalysis(skills=["Python", "SQL"], technologies=["Docker"])
    )
    jd_result = JDAnalysisResult(
        analysis=JDAnalysis(
            role="Software Engineer",
            required_skills=["Python", "SQL"],
            preferred_skills=["Kubernetes"],
            technologies=["Docker", "Kubernetes"],
        ),
        blueprint=InterviewBlueprint(),
    )

    monkeypatch.setattr(main, "client", object())
    monkeypatch.setattr(main, "analyze_resume", lambda client, model_name, resume_text: resume_result)
    monkeypatch.setattr(main, "analyze_job_description", lambda client, model_name, jd_text: jd_result)

    response = TestClient(main.app).post(
        "/resume/match-jd",
        json={
            "resume_text": "Python developer with SQL and Docker experience on software projects.",
            "jd_text": "Software Engineer requiring Python and SQL experience.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["match_score"] == 75
    assert body["matched_required_skills"] == ["Python", "SQL"]
    assert body["missing_preferred_skills"] == ["Kubernetes"]
    assert body["matched_technologies"] == ["Docker"]


def test_resume_jd_endpoint_requires_gemini(monkeypatch):
    monkeypatch.setattr(main, "client", None)
    response = TestClient(main.app).post(
        "/resume/match-jd",
        json={
            "resume_text": "Python developer with SQL and Docker experience on software projects.",
            "jd_text": "Software Engineer requiring Python and SQL experience.",
        },
    )
    assert response.status_code == 503
