import json
import sqlite3
from pathlib import Path

from models import AnswerRequest, InterviewEvaluation
from security import hash_token, utc_now, verify_token

DB_PATH = Path(__file__).parent / "history.db"


def normalize_candidate_id(candidate_id: str) -> str:
    return candidate_id.strip().lower()


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                candidate_id TEXT,
                role TEXT,
                difficulty TEXT,
                question TEXT,
                score INTEGER,
                technical_accuracy INTEGER,
                relevance INTEGER,
                clarity INTEGER,
                completeness INTEGER,
                confidence REAL,
                needs_human_review INTEGER,
                weaknesses TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_candidate_id ON evaluations (candidate_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON evaluations (session_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_access (
                candidate_id TEXT PRIMARY KEY,
                access_token_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                session_token_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_candidate ON sessions (candidate_id)")


def ensure_candidate_access(candidate_id: str, access_token: str | None = None) -> tuple[str, bool]:
    candidate_id = normalize_candidate_id(candidate_id)
    if not candidate_id:
        raise ValueError("candidate_id is required")
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT access_token_hash FROM candidate_access WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if row:
            if not access_token or not verify_token(access_token, row[0]):
                raise PermissionError("Invalid candidate access token")
            return access_token, False

        from security import generate_token
        token = generate_token()
        conn.execute(
            "INSERT INTO candidate_access (candidate_id, access_token_hash, created_at) VALUES (?,?,?)",
            (candidate_id, hash_token(token), utc_now()),
        )
        return token, True


def create_session(session_id: str, candidate_id: str, session_token: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        now = utc_now()
        conn.execute(
            "INSERT INTO sessions (session_id, candidate_id, session_token_hash, created_at, last_seen_at) VALUES (?,?,?,?,?)",
            (session_id, normalize_candidate_id(candidate_id), hash_token(session_token), now, now),
        )


def authorize_session(session_id: str, session_token: str, candidate_id: str | None = None) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT candidate_id, session_token_hash FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row or not verify_token(session_token, row[1]):
            return False
        if candidate_id is not None and normalize_candidate_id(candidate_id) != row[0]:
            return False
        conn.execute("UPDATE sessions SET last_seen_at = ? WHERE session_id = ?", (utc_now(), session_id))
        return True


def authorize_candidate(candidate_id: str, access_token: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT access_token_hash FROM candidate_access WHERE candidate_id = ?",
            (normalize_candidate_id(candidate_id),),
        ).fetchone()
        return bool(row and verify_token(access_token, row[0]))


def save_evaluation(data: AnswerRequest, evaluation: InterviewEvaluation) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO evaluations (
                session_id, candidate_id, role, difficulty, question, score,
                technical_accuracy, relevance, clarity, completeness,
                confidence, needs_human_review, weaknesses
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                data.session_id or "anonymous",
                normalize_candidate_id(data.candidate_id) or "anonymous",
                data.role,
                data.difficulty,
                data.question,
                evaluation.score,
                evaluation.technical_accuracy,
                evaluation.relevance,
                evaluation.clarity,
                evaluation.completeness,
                evaluation.confidence,
                int(evaluation.needs_human_review),
                json.dumps(evaluation.weaknesses),
            ),
        )


def get_session_history(session_id: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM evaluations WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_candidate_history(candidate_id: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM evaluations WHERE candidate_id = ? ORDER BY id ASC",
            (normalize_candidate_id(candidate_id),),
        ).fetchall()
        return [dict(row) for row in rows]


def get_candidate_summary(candidate_id: str) -> dict:
    history = get_candidate_history(candidate_id)
    if not history:
        return {"candidate_id": normalize_candidate_id(candidate_id), "sessions": [], "total_answers": 0}

    sessions: dict[str, list[dict]] = {}
    for row in history:
        sessions.setdefault(row["session_id"], []).append(row)

    session_summaries = []
    for session_id, rows in sessions.items():
        avg_score = round(sum(r["score"] for r in rows) / len(rows), 1)
        session_summaries.append(
            {
                "session_id": session_id,
                "answered": len(rows),
                "average_score": avg_score,
                "started_at": rows[0]["created_at"],
            }
        )

    all_weaknesses = []
    for row in history:
        try:
            all_weaknesses.extend(json.loads(row["weaknesses"] or "[]"))
        except (json.JSONDecodeError, TypeError):
            if row["weaknesses"]:
                all_weaknesses.extend(w for w in row["weaknesses"].split(",") if w.strip())
    weakness_counts: dict[str, int] = {}
    for w in all_weaknesses:
        weakness_counts[w] = weakness_counts.get(w, 0) + 1
    recurring_weaknesses = sorted(weakness_counts.items(), key=lambda kv: -kv[1])[:5]

    return {
        "candidate_id": normalize_candidate_id(candidate_id),
        "total_answers": len(history),
        "sessions": session_summaries,
        "recurring_weaknesses": [w for w, _count in recurring_weaknesses],
    }
