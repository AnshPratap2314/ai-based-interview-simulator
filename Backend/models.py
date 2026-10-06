from enum import Enum
from typing import List
from pydantic import BaseModel, Field, field_validator


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class AnswerRequest(BaseModel):
    session_id: str = Field(default="", max_length=100)
    candidate_id: str = Field(default="", max_length=150)
    role: str = Field(default="Technical Interview", max_length=200)
    difficulty: Difficulty = Difficulty.medium
    job_description: str = Field(default="", max_length=10000)
    question: str = Field(min_length=1, max_length=5000)
    answer: str = Field(min_length=1, max_length=12000)
    expected_skills: List[str] = Field(default_factory=list, max_length=20)

    @field_validator("session_id", "candidate_id", "role", "job_description", "question", "answer")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator("expected_skills")
    @classmethod
    def validate_skills(cls, value: List[str]) -> List[str]:
        cleaned = []
        for skill in value:
            if not isinstance(skill, str):
                raise ValueError("Each skill must be a string.")
            skill = skill.strip()
            if not skill:
                continue
            if len(skill) > 100:
                raise ValueError("Each skill must be 100 characters or fewer.")
            cleaned.append(skill)
        return cleaned


class SkillAssessment(BaseModel):
    skill: str = Field(min_length=1, max_length=100)
    score: int = Field(ge=0, le=10)


class InterviewEvaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    technical_accuracy: int = Field(ge=1, le=10)
    relevance: int = Field(ge=1, le=10)
    clarity: int = Field(ge=1, le=10)
    completeness: int = Field(ge=1, le=10)
    strengths: List[str] = Field(default_factory=list, max_length=20)
    weaknesses: List[str] = Field(default_factory=list, max_length=20)
    evidence: List[str] = Field(default_factory=list, max_length=20)
    feedback: str = Field(default="", max_length=5000)
    improved_answer: str = Field(default="", max_length=8000)
    skills_assessed: List[SkillAssessment] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1)
    needs_human_review: bool

    @field_validator("strengths", "weaknesses", "evidence")
    @classmethod
    def validate_feedback_lists(cls, value: List[str]) -> List[str]:
        cleaned = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("Feedback list items must be strings.")
            item = item.strip()
            if len(item) > 500:
                raise ValueError("Feedback items must be 500 characters or fewer.")
            cleaned.append(item)
        return cleaned
class InterviewStartRequest(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=150)
    session_id: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=200)
    interview_type: str = Field(default="technical", max_length=30)
    difficulty: Difficulty = Difficulty.medium
    question_count: int = Field(default=5, ge=1, le=50)

    @field_validator(
        "candidate_id",
        "session_id",
        "role",
        "interview_type",
    )
    @classmethod
    def normalize_interview_fields(cls, value: str) -> str:
        return value.strip()


class InterviewQuestionResponse(BaseModel):
    id: str
    question: str
    skills: List[str]
    question_number: int
    total_questions: int


class InterviewStartResponse(BaseModel):
    session_id: str
    candidate_id: str
    role: str
    interview_type: str
    difficulty: Difficulty
    question_count: int
    question: InterviewQuestionResponse