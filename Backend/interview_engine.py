
from __future__ import annotations

import json
import random
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

from storage import DB_PATH, init_db


class InterviewType(str, Enum):
    technical = "technical"
    hr = "hr"
    aiml = "aiml"


@dataclass(frozen=True)
class InterviewConfig:
    role: str
    interview_type: InterviewType
    difficulty: str
    question_count: int

    def validate(self) -> None:
        role = self.role.strip()

        if not role:
            raise ValueError("Role is required.")

        # Validate interview type explicitly.
        if not isinstance(self.interview_type, InterviewType):
            raise ValueError(
                "Interview type must be technical, hr, or aiml."
            )

        if self.difficulty not in {"easy", "medium", "hard"}:
            raise ValueError(
                "Difficulty must be easy, medium, or hard."
            )

        if self.question_count < 1 or self.question_count > 50:
            raise ValueError(
                "Question count must be between 1 and 50."
            )


@dataclass(frozen=True)
class InterviewQuestion:
    id: str
    text: str
    interview_type: InterviewType
    difficulty: str
    skills: tuple[str, ...] = ()


@dataclass
class InterviewState:
    session_id: str
    candidate_id: str
    config: InterviewConfig
    questions: list[InterviewQuestion] = field(default_factory=list)
    current_index: int = 0
    answered_question_ids: list[str] = field(default_factory=list)

    @property
    def completed(self) -> bool:
        return self.current_index >= len(self.questions)

    @property
    def current_question(self) -> InterviewQuestion | None:
        if self.completed:
            return None

        return self.questions[self.current_index]

    @property
    def answered_count(self) -> int:
        return len(self.answered_question_ids)

    @property
    def remaining_count(self) -> int:
        return max(
            0,
            len(self.questions) - self.current_index,
        )



def _interview_state_connect() -> sqlite3.Connection:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_interview_state_db() -> None:
    """Create the durable interview-state table if it does not exist."""
    conn = _interview_state_connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_states (
                session_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                role TEXT NOT NULL,
                interview_type TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                question_count INTEGER NOT NULL,
                questions_json TEXT NOT NULL,
                current_index INTEGER NOT NULL DEFAULT 0,
                answered_question_ids_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_interview_states_candidate
            ON interview_states(candidate_id)
            """
        )
        conn.commit()
    finally:
        conn.close()


def _serialize_question(question: InterviewQuestion) -> dict:
    return {
        "id": question.id,
        "text": question.text,
        "interview_type": question.interview_type.value,
        "difficulty": question.difficulty,
        "skills": list(question.skills),
    }


def _deserialize_question(data: dict) -> InterviewQuestion:
    return InterviewQuestion(
        id=str(data["id"]),
        text=str(data["text"]),
        interview_type=InterviewType(data["interview_type"]),
        difficulty=str(data["difficulty"]),
        skills=tuple(str(skill) for skill in data.get("skills", [])),
    )


def save_interview_state(state: InterviewState) -> None:
    """Persist the complete interview state atomically."""
    init_interview_state_db()
    questions_json = json.dumps(
        [_serialize_question(question) for question in state.questions],
        separators=(",", ":"),
    )
    answered_json = json.dumps(
        state.answered_question_ids,
        separators=(",", ":"),
    )

    conn = _interview_state_connect()
    try:
        conn.execute(
            """
            INSERT INTO interview_states (
                session_id,
                candidate_id,
                role,
                interview_type,
                difficulty,
                question_count,
                questions_json,
                current_index,
                answered_question_ids_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                candidate_id = excluded.candidate_id,
                role = excluded.role,
                interview_type = excluded.interview_type,
                difficulty = excluded.difficulty,
                question_count = excluded.question_count,
                questions_json = excluded.questions_json,
                current_index = excluded.current_index,
                answered_question_ids_json = excluded.answered_question_ids_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                state.session_id,
                state.candidate_id,
                state.config.role,
                state.config.interview_type.value,
                state.config.difficulty,
                len(state.questions),
                questions_json,
                state.current_index,
                answered_json,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def load_interview_state(
    session_id: str,
    candidate_id: Optional[str] = None,
) -> Optional[InterviewState]:
    """Restore an interview state from SQLite after process restart."""
    init_interview_state_db()
    conn = _interview_state_connect()
    try:
        row = conn.execute(
            """
            SELECT
                session_id,
                candidate_id,
                role,
                interview_type,
                difficulty,
                question_count,
                questions_json,
                current_index,
                answered_question_ids_json
            FROM interview_states
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    if candidate_id is not None and row["candidate_id"] != candidate_id:
        return None

    questions_data = json.loads(row["questions_json"])
    answered_ids = json.loads(row["answered_question_ids_json"])

    config = InterviewConfig(
        role=row["role"],
        interview_type=InterviewType(row["interview_type"]),
        difficulty=row["difficulty"],
        question_count=int(row["question_count"]),
    )

    return InterviewState(
        session_id=row["session_id"],
        candidate_id=row["candidate_id"],
        config=config,
        questions=[_deserialize_question(item) for item in questions_data],
        current_index=int(row["current_index"]),
        answered_question_ids=[str(item) for item in answered_ids],
    )


class QuestionBank:
    """
    Backend-owned question bank.

    The evaluator remains completely separate from question selection.
    """

    def __init__(self) -> None:
        self._questions = self._build_questions()

    @staticmethod
    def _build_questions() -> list[InterviewQuestion]:
        return [
            # =========================================================
            # TECHNICAL — EASY
            # =========================================================
            InterviewQuestion(
                "technical-easy-001",
                "What is OOP?",
                InterviewType.technical,
                "easy",
                ("OOP",),
            ),
            InterviewQuestion(
                "technical-easy-002",
                "What is DBMS?",
                InterviewType.technical,
                "easy",
                ("DBMS", "database"),
            ),

            # =========================================================
            # TECHNICAL — MEDIUM
            # =========================================================
            InterviewQuestion(
                "technical-medium-001",
                "Explain normalization in DBMS.",
                InterviewType.technical,
                "medium",
                ("DBMS", "normalization"),
            ),
            InterviewQuestion(
                "technical-medium-002",
                "What is the difference between authentication and authorization?",
                InterviewType.technical,
                "medium",
                ("authentication", "authorization"),
            ),

            # =========================================================
            # TECHNICAL — HARD
            # =========================================================
            InterviewQuestion(
                "technical-hard-001",
                "How would you design a scalable backend service?",
                InterviewType.technical,
                "hard",
                ("system design", "scalability"),
            ),
            InterviewQuestion(
                "technical-hard-002",
                "How would you detect and prevent data leakage in a machine learning pipeline?",
                InterviewType.technical,
                "hard",
                ("machine learning", "data leakage"),
            ),

            # =========================================================
            # HR — EASY
            # =========================================================
            InterviewQuestion(
                "hr-easy-001",
                "Tell me about yourself.",
                InterviewType.hr,
                "easy",
                ("communication",),
            ),
            InterviewQuestion(
                "hr-easy-002",
                "What are your strengths?",
                InterviewType.hr,
                "easy",
                ("self-awareness",),
            ),

            # =========================================================
            # HR — MEDIUM
            # =========================================================
            InterviewQuestion(
                "hr-medium-001",
                "Tell me about a time you solved a difficult problem.",
                InterviewType.hr,
                "medium",
                ("problem solving",),
            ),
            InterviewQuestion(
                "hr-medium-002",
                "Tell me about a time you demonstrated leadership.",
                InterviewType.hr,
                "medium",
                ("leadership",),
            ),

            # =========================================================
            # HR — HARD
            # =========================================================
            InterviewQuestion(
                "hr-hard-001",
                "How would you handle disagreement with your manager?",
                InterviewType.hr,
                "hard",
                ("conflict resolution",),
            ),

            # =========================================================
            # AI/ML — EASY
            # =========================================================
            InterviewQuestion(
                "aiml-easy-001",
                "What is Machine Learning?",
                InterviewType.aiml,
                "easy",
                ("machine learning",),
            ),
            InterviewQuestion(
                "aiml-easy-002",
                "What is supervised learning?",
                InterviewType.aiml,
                "easy",
                ("supervised learning",),
            ),

            # =========================================================
            # AI/ML — MEDIUM
            # =========================================================
            InterviewQuestion(
                "aiml-medium-001",
                "Explain bias and variance.",
                InterviewType.aiml,
                "medium",
                ("bias", "variance"),
            ),
            InterviewQuestion(
                "aiml-medium-002",
                "Explain precision, recall and F1-score.",
                InterviewType.aiml,
                "medium",
                ("precision", "recall", "F1"),
            ),

            # =========================================================
            # AI/ML — HARD
            # =========================================================
            InterviewQuestion(
                "aiml-hard-001",
                "Explain how backpropagation works.",
                InterviewType.aiml,
                "hard",
                ("neural networks", "backpropagation"),
            ),
            InterviewQuestion(
                "aiml-hard-002",
                "How would you design an end-to-end ML system?",
                InterviewType.aiml,
                "hard",
                ("machine learning", "system design"),
            ),
        ]

    def get_questions(
        self,
        interview_type: InterviewType,
        difficulty: str,
    ) -> list[InterviewQuestion]:
        return [
            question
            for question in self._questions
            if question.interview_type == interview_type
            and question.difficulty == difficulty
        ]


class InterviewEngine:
    """
    Orchestrates an interview session.

    Responsibilities:
    - validate interview configuration
    - select questions
    - maintain interview state
    - prevent duplicate questions inside one interview
    - advance the interview after an answer

    It deliberately does NOT evaluate answers.
    """

    def __init__(
        self,
        question_bank: QuestionBank | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.question_bank = question_bank or QuestionBank()
        self.rng = rng or random.Random()

    def create_session(
        self,
        session_id: str,
        candidate_id: str,
        config: InterviewConfig,
        previous_question_ids: Sequence[str] = (),
    ) -> InterviewState:
        config.validate()

        questions = self.question_bank.get_questions(
            config.interview_type,
            config.difficulty,
        )

        if not questions:
            raise ValueError(
                f"No questions available for "
                f"{config.interview_type.value}/"
                f"{config.difficulty}."
            )

        previous = set(previous_question_ids)

        fresh = [
            question
            for question in questions
            if question.id not in previous
        ]

        # Prefer questions that were not used in recent sessions.
        candidates = fresh or questions

        selected = self._select_questions(
            candidates,
            config.question_count,
        )

        return InterviewState(
            session_id=session_id,
            candidate_id=candidate_id,
            config=config,
            questions=selected,
        )

    def mark_answered(
        self,
        state: InterviewState,
    ) -> InterviewQuestion:
        question = state.current_question

        if question is None:
            raise ValueError(
                "Interview is already complete."
            )

        state.answered_question_ids.append(question.id)
        state.current_index += 1

        return question

    def _select_questions(
        self,
        questions: Sequence[InterviewQuestion],
        question_count: int,
    ) -> list[InterviewQuestion]:
        items = list(questions)

        self.rng.shuffle(items)

        # Never repeat a question inside one interview.
        #
        # If the question bank contains fewer questions than requested,
        # return all available unique questions instead of cycling.
        return items[:question_count]
