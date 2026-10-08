from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterable

from interview_engine import InterviewConfig, InterviewQuestion, InterviewState, InterviewType
from personalized_interview import PersonalizedInterviewPlan


RUNTIME_DB_PATH = Path(
    os.getenv(
        "INTERVIEW_RUNTIME_DB_PATH",
        str(Path(__file__).resolve().parent / "interview_runtime.db"),
    )
)


def init_real_interview_db() -> None:
    RUNTIME_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(RUNTIME_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS live_interview_answers (
                session_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                evaluation_id TEXT NOT NULL,
                score REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_id, question_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_live_answers_session "
            "ON live_interview_answers(session_id)"
        )
        conn.commit()


def save_live_answer(
    session_id: str,
    candidate_id: str,
    question_id: str,
    evaluation_id: str,
    score: float,
) -> None:
    init_real_interview_db()
    with sqlite3.connect(RUNTIME_DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO live_interview_answers
            (session_id, candidate_id, question_id, evaluation_id, score)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, candidate_id, question_id, evaluation_id, float(score)),
        )
        conn.commit()


def get_live_answers(session_id: str, candidate_id: str) -> list[dict]:
    init_real_interview_db()
    with sqlite3.connect(RUNTIME_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT question_id, evaluation_id, score, created_at
            FROM live_interview_answers
            WHERE session_id = ? AND candidate_id = ?
            ORDER BY created_at ASC, question_id ASC
            """,
            (session_id, candidate_id),
        ).fetchall()
    return [dict(row) for row in rows]


def _question_id(index: int, topic: str) -> str:
    safe = "".join(
        char.lower() if char.isalnum() else "-"
        for char in topic
    ).strip("-")
    safe = safe[:60] or "question"
    return f"personalized-{index:03d}-{safe}"


def state_from_plan(
    session_id: str,
    candidate_id: str,
    plan: PersonalizedInterviewPlan,
) -> InterviewState:
    questions = [
        InterviewQuestion(
            id=_question_id(index, item.topic),
            text=item.question,
            interview_type=InterviewType.technical,
            difficulty="hard" if item.priority == "high" else "medium",
            skills=(item.topic,),
        )
        for index, item in enumerate(plan.questions, start=1)
    ]

    if not questions:
        raise ValueError("Personalized interview plan contains no questions.")

    config = InterviewConfig(
        role=plan.role,
        interview_type=InterviewType.technical,
        difficulty=(
            "hard"
            if any(item.priority == "high" for item in plan.questions)
            else "medium"
        ),
        question_count=len(questions),
    )
    config.validate()

    return InterviewState(
        session_id=session_id,
        candidate_id=candidate_id,
        config=config,
        questions=questions,
    )


def current_question_payload(state: InterviewState) -> dict | None:
    question = state.current_question
    if question is None:
        return None
    return {
        "id": question.id,
        "question": question.text,
        "skills": list(question.skills),
        "question_number": state.current_index + 1,
        "total_questions": len(state.questions),
    }


def advance_after_answer(state: InterviewState, question_id: str) -> InterviewState:
    current = state.current_question
    if current is None:
        raise ValueError("Interview is already completed.")
    if current.id != question_id:
        raise ValueError("The answered question does not match the current question.")

    state.answered_question_ids.append(current.id)
    state.current_index += 1
    return state


def _unique(values: Iterable[str], limit: int = 5) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value).strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
        if len(result) >= limit:
            break
    return result


def build_final_report(session_id: str, candidate_id: str) -> dict:
    answers = get_live_answers(session_id, candidate_id)
    if not answers:
        return {
            "completed": False,
            "questions_answered": 0,
            "average_score": None,
            "highest_score": None,
            "lowest_score": None,
        }

    scores = [float(item["score"]) for item in answers]
    return {
        "completed": True,
        "questions_answered": len(scores),
        "average_score": round(sum(scores) / len(scores), 2),
        "highest_score": max(scores),
        "lowest_score": min(scores),
    }
