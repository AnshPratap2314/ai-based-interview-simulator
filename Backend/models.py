from typing import List
from pydantic import BaseModel, Field


class AnswerRequest(BaseModel):
    session_id: str = Field(default="", max_length=100)
    candidate_id: str = Field(default="", max_length=150)
    role: str = Field(default="Technical Interview", max_length=200)
    difficulty: str = Field(default="medium", max_length=30)
    job_description: str = Field(default="", max_length=10000)
    question: str = Field(min_length=1, max_length=5000)
    answer: str = Field(min_length=1, max_length=12000)
    expected_skills: List[str] = Field(default_factory=list, max_length=20)


class SkillAssessment(BaseModel):
    skill: str
    score: int = Field(ge=0, le=10)


class InterviewEvaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    technical_accuracy: int = Field(ge=1, le=10)
    relevance: int = Field(ge=1, le=10)
    clarity: int = Field(ge=1, le=10)
    completeness: int = Field(ge=1, le=10)
    strengths: List[str]
    weaknesses: List[str]
    evidence: List[str]
    feedback: str
    improved_answer: str
    skills_assessed: List[SkillAssessment]
    confidence: float = Field(ge=0, le=1)
    needs_human_review: bool