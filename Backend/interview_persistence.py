from __future__ import annotations

import json
import sqlite3
from typing import Optional

from interview_engine import (
    InterviewConfig,
    InterviewQuestion,
    InterviewState,
    InterviewType,
)
from storage import DB_PATH, init_db


def _connect() -> sqlite3.Connection:
    init_db()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_interview_state_db() -> None:
    """
    Create the persistent interview-state table.

    State is stored separately from evaluation/history data so this
    feature does not modify the existing evaluation schema.
    """
    conn = _connect()

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
    """
    Atomically save the complete interview state.

    The complete question list is stored so a backend restart does not
    require regenerating the interview or relying on in-memory state.
    """
    init_interview_state_db()

    questions_json = json.dumps(
        [_serialize_question(question) for question in state.questions],
        separators=(",", ":"),
    )

    answered_json = json.dumps(
        state.answered_question_ids,
        separators=(",", ":"),
    )

    conn = _connect()

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
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(session_id) DO UPDATE SET
                candidate_id = excluded.candidate_id,
                role = excluded.role,
                interview_type = excluded.interview_type,
                difficulty = excluded.difficulty,
                question_count = excluded.question_count,
                questions_json = excluded.questions_json,
                current_index = excluded.current_index,
                answered_question_ids_json =
                    excluded.answered_question_ids_json,
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


def get_interview_state(
    session_id: str,
    candidate_id: Optional[str] = None,
) -> Optional[InterviewState]:
    """
    Restore an interview state from SQLite.

    candidate_id is checked when supplied so one candidate cannot load
    another candidate's interview state.
    """
    init_interview_state_db()

    conn = _connect()

    try:
        row = conn.execute(
            """
            SELECT
                session_id,
                candidate_id,
                role,
                interview_type,
                difficulty,
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
        questions=[
            _deserialize_question(question)
            for question in questions_data
        ],
        current_index=int(row["current_index"]),
        answered_question_ids=[
            str(question_id)
            for question_id in answered_ids
        ],
    )


def delete_interview_state(session_id: str) -> None:
    init_interview_state_db()

    conn = _connect()

    try:
        conn.execute(
            """
            DELETE FROM interview_states
            WHERE session_id = ?
            """,
            (session_id,),
        )
        conn.commit()
    finally:
        conn.close()