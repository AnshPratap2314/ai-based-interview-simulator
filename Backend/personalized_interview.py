from __future__ import annotations

import re
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from jd_parser import JDAnalysis
from resume_parser import ResumeAnalysis, ResumeJDMatch


class PersonalizedQuestionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: str = Field(pattern=r"^(high|medium|low)$")
    category: str = Field(pattern=r"^(gap|strength|responsibility|behavioral)$")
    topic: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=1000)
    evidence_source: str = Field(min_length=1, max_length=500)


class PersonalizedInterviewPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1, max_length=200)
    total_questions: int = Field(ge=1, le=50)
    focus_areas: list[str] = Field(default_factory=list, max_length=30)
    gap_topics: list[str] = Field(default_factory=list, max_length=30)
    strength_topics: list[str] = Field(default_factory=list, max_length=30)
    questions: list[PersonalizedQuestionPlan] = Field(min_length=1, max_length=50)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", " ", _clean(value).casefold()).strip()


def _unique(values: Iterable[str], limit: int = 30) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _clean(value)
        key = _key(cleaned)
        if key and key not in seen:
            seen.add(key)
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _question_for_gap(topic: str, role: str) -> tuple[str, str]:
    return (
        f"Explain how you would use {topic} in a {role} project. Include your design choices, trade-offs, and how you would validate the result.",
        f"Assess whether the candidate can apply the missing required skill {topic} rather than only define it.",
    )


def _question_for_strength(topic: str) -> tuple[str, str]:
    return (
        f"You list {topic} as part of your background. Describe a project where you used it, what problem you solved, and one technical decision you made.",
        f"Verify the candidate's depth of evidence for the matched skill {topic}.",
    )


def _question_for_responsibility(topic: str, role: str) -> tuple[str, str]:
    return (
        f"As a {role}, how would you approach this responsibility: {topic}? Walk through your process, key decisions, and how you would measure success.",
        f"Test the candidate's ability to translate the JD responsibility {topic} into an engineering approach.",
    )


def _question_for_behavioral(topic: str) -> tuple[str, str]:
    return (
        f"Tell me about a time you demonstrated {topic}. What was the situation, what did you do, and what was the outcome?",
        f"Assess behavioral evidence for the JD topic {topic}.",
    )


def build_personalized_interview_plan(
    resume: ResumeAnalysis,
    jd: JDAnalysis,
    match: ResumeJDMatch,
    question_count: int = 10,
) -> PersonalizedInterviewPlan:
    count = max(1, min(50, int(question_count)))
    role = _clean(jd.role or resume.target_role or "Software Engineer")

    questions: list[PersonalizedQuestionPlan] = []
    used_topics: set[str] = set()

    def add(
        priority: str,
        category: str,
        topic: str,
        question: str,
        objective: str,
        evidence_source: str,
    ) -> None:
        topic_clean = _clean(topic)
        topic_key = _key(topic_clean)
        if not topic_key or topic_key in used_topics or len(questions) >= count:
            return
        used_topics.add(topic_key)
        questions.append(
            PersonalizedQuestionPlan(
                priority=priority,
                category=category,
                topic=topic_clean,
                objective=objective,
                question=question,
                evidence_source=evidence_source,
            )
        )

    # Highest priority: requirements for which the resume has no evidence.
    for topic in match.missing_required_skills:
        question, objective = _question_for_gap(topic, role)
        add("high", "gap", topic, question, objective, "JD required skill missing from resume evidence")

    for topic in match.missing_technologies:
        question, objective = _question_for_gap(topic, role)
        add("high", "gap", topic, question, objective, "JD technology missing from resume evidence")

    # Validate claimed strengths with project-level questions.
    for topic in match.matched_required_skills:
        question, objective = _question_for_strength(topic)
        add("medium", "strength", topic, question, objective, "JD required skill matched by resume evidence")

    # Test actual job responsibilities, not only keywords.
    for topic in jd.responsibilities:
        question, objective = _question_for_responsibility(topic, role)
        add("medium", "responsibility", topic, question, objective, "JD responsibility")

    for topic in jd.behavioral_topics if hasattr(jd, "behavioral_topics") else []:
        question, objective = _question_for_behavioral(topic)
        add("medium", "behavioral", topic, question, objective, "JD behavioral topic")

    # Fall back to technical/domain topics so a complete resume still receives a useful plan.
    for topic in jd.required_skills + jd.technologies + jd.domain:
        question, objective = _question_for_strength(topic)
        add("low", "strength", topic, question, objective, "JD topic")

    if not questions:
        topic = resume.target_role or role
        question, objective = _question_for_strength(topic)
        add("low", "strength", topic, question, objective, "Candidate target role")

    gap_topics = _unique(match.missing_required_skills + match.missing_technologies)
    strength_topics = _unique(match.matched_required_skills + match.matched_technologies)
    focus_areas = _unique(gap_topics + strength_topics + jd.responsibilities + jd.technologies)

    return PersonalizedInterviewPlan(
        role=role,
        total_questions=len(questions),
        focus_areas=focus_areas,
        gap_topics=gap_topics,
        strength_topics=strength_topics,
        questions=questions,
    )
