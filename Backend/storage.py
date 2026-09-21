import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from models import AnswerRequest, InterviewEvaluation
from security import generate_token, hash_token, utc_now, verify_token

DB_PATH = Path(os.getenv("INTERVIEW_DB_PATH", "history.db"))
if not DB_PATH.is_absolute():
    DB_PATH = Path(__file__).parent / DB_PATH
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


SESSION_TTL_HOURS = _env_int("SESSION_TTL_HOURS", 4)
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


def normalize_candidate_id(candidate_id: str) -> str:
    if not isinstance(candidate_id, str):
        return ""
    return candidate_id.strip().lower()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
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
                strengths TEXT DEFAULT '[]',
                weaknesses TEXT DEFAULT '[]',
                evidence TEXT DEFAULT '[]',
                feedback TEXT DEFAULT '',
                improved_answer TEXT DEFAULT '',
                skills_assessed TEXT DEFAULT '[]',
                evaluation_json TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _add_column_if_missing(conn, "evaluations", "request_id", "TEXT")
        _add_column_if_missing(conn, "evaluations", "strengths", "TEXT DEFAULT '[]'")
        _add_column_if_missing(conn, "evaluations", "evidence", "TEXT DEFAULT '[]'")
        _add_column_if_missing(conn, "evaluations", "feedback", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "evaluations", "improved_answer", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "evaluations", "skills_assessed", "TEXT DEFAULT '[]'")
        _add_column_if_missing(conn, "evaluations", "evaluation_json", "TEXT DEFAULT '{}'")
        conn.execute("DROP INDEX IF EXISTS idx_evaluations_request_id")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_evaluations_request_session ON evaluations (request_id, session_id) WHERE request_id IS NOT NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_candidate_id ON evaluations (candidate_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON evaluations (session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evaluations_candidate_created ON evaluations (candidate_id, id)")
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
                last_seen_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "expires_at" not in columns:
            default_expiry = (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat().replace("'", "''")
            conn.execute(f"ALTER TABLE sessions ADD COLUMN expires_at TEXT NOT NULL DEFAULT '{default_expiry}'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_candidate ON sessions (candidate_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions (expires_at)")


def check_database() -> bool:
    try:
        with _connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except (sqlite3.Error, OSError):
        return False


def ensure_candidate_access(candidate_id: str, access_token: str | None = None) -> tuple[str, bool]:
    candidate_id = normalize_candidate_id(candidate_id)
    if not candidate_id:
        raise ValueError("candidate_id is required")
    if access_token is not None and not isinstance(access_token, str):
        raise ValueError("access_token must be a string")
    with _connect() as conn:
        row = conn.execute("SELECT access_token_hash FROM candidate_access WHERE candidate_id = ?", (candidate_id,)).fetchone()
        if row:
            if not access_token or not verify_token(access_token, row[0]):
                raise PermissionError("Invalid candidate access token")
            return access_token, False
        token = generate_token()
        conn.execute(
            "INSERT INTO candidate_access (candidate_id, access_token_hash, created_at) VALUES (?,?,?)",
            (candidate_id, hash_token(token), utc_now()),
        )
        return token, True


def create_session(session_id: str, candidate_id: str) -> str:
    session_id = session_id.strip()
    candidate_id = normalize_candidate_id(candidate_id)
    if not session_id:
        raise ValueError("session_id is required")
    if not candidate_id:
        raise ValueError("candidate_id is required")
    session_token = generate_token()
    with _connect() as conn:
        now = datetime.now(timezone.utc)
        conn.execute(
            "INSERT INTO sessions (session_id, candidate_id, session_token_hash, created_at, last_seen_at, expires_at) VALUES (?,?,?,?,?,?)",
            (session_id, candidate_id, hash_token(session_token), now.isoformat(), now.isoformat(), (now + timedelta(hours=SESSION_TTL_HOURS)).isoformat()),
        )
    return session_token


def authorize_session(session_id: str, session_token: str, candidate_id: str | None = None) -> bool:
    if not isinstance(session_id, str) or not session_id.strip() or not isinstance(session_token, str) or not session_token:
        return False
    with _connect() as conn:
        row = conn.execute("SELECT candidate_id, session_token_hash, expires_at FROM sessions WHERE session_id = ?", (session_id.strip(),)).fetchone()
        if not row or not verify_token(session_token, row[1]):
            return False
        try:
            expires_at = datetime.fromisoformat(row[2])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return False
        if expires_at <= datetime.now(timezone.utc):
            return False
        if candidate_id is not None and normalize_candidate_id(candidate_id) != row[0]:
            return False
        conn.execute("UPDATE sessions SET last_seen_at = ? WHERE session_id = ?", (utc_now(), session_id.strip()))
        return True


def authorize_candidate(candidate_id: str, access_token: str) -> bool:
    if not isinstance(access_token, str) or not access_token:
        return False
    normalized = normalize_candidate_id(candidate_id)
    if not normalized:
        return False
    with _connect() as conn:
        row = conn.execute("SELECT access_token_hash FROM candidate_access WHERE candidate_id = ?", (normalized,)).fetchone()
        return bool(row and verify_token(access_token, row[0]))


def save_evaluation(data: AnswerRequest, evaluation: InterviewEvaluation, request_id: str) -> tuple[InterviewEvaluation, bool]:
    normalized = normalize_candidate_id(data.candidate_id)
    evaluation_json = evaluation.model_dump_json()
    values = (
        request_id, data.session_id, normalized, data.role, data.difficulty.value, data.question,
        evaluation.score, evaluation.technical_accuracy, evaluation.relevance, evaluation.clarity,
        evaluation.completeness, evaluation.confidence, int(evaluation.needs_human_review),
        json.dumps(evaluation.strengths, ensure_ascii=False), json.dumps(evaluation.weaknesses, ensure_ascii=False),
        json.dumps(evaluation.evidence, ensure_ascii=False), evaluation.feedback, evaluation.improved_answer,
        json.dumps([item.model_dump() for item in evaluation.skills_assessed], ensure_ascii=False), evaluation_json,
    )
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO evaluations (
                request_id, session_id, candidate_id, role, difficulty, question, score,
                technical_accuracy, relevance, clarity, completeness, confidence, needs_human_review,
                strengths, weaknesses, evidence, feedback, improved_answer, skills_assessed, evaluation_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, values,
        )
        row = conn.execute("SELECT evaluation_json FROM evaluations WHERE request_id = ? AND session_id = ? AND candidate_id = ?", (request_id, data.session_id, normalized)).fetchone()
        if not row:
            raise sqlite3.DatabaseError("Unable to persist evaluation")
        try:
            stored = InterviewEvaluation.model_validate(json.loads(row[0]))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise sqlite3.DatabaseError("Stored evaluation is invalid") from exc
        return stored, stored.model_dump() == evaluation.model_dump()


def get_evaluation_by_request_id(request_id: str, session_id: str, candidate_id: str) -> InterviewEvaluation | None:
    if not isinstance(request_id, str) or not request_id or not isinstance(session_id, str) or not session_id:
        return None
    normalized = normalize_candidate_id(candidate_id)
    with _connect() as conn:
        row = conn.execute("SELECT evaluation_json FROM evaluations WHERE request_id = ? AND session_id = ? AND candidate_id = ?", (request_id, session_id.strip(), normalized)).fetchone()
    if not row:
        return None
    try:
        return InterviewEvaluation.model_validate(json.loads(row[0]))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _clamp_page(page: int, page_size: int) -> tuple[int, int]:
    return max(1, page), min(MAX_PAGE_SIZE, max(1, page_size))


def _decode_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    raw = item.get("evaluation_json")
    if raw:
        try:
            item["evaluation"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            item["evaluation"] = None
    return item


def get_session_history(session_id: str, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    page, page_size = _clamp_page(page, page_size)
    offset = (page - 1) * page_size
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) FROM evaluations WHERE session_id = ?", (session_id,)).fetchone()[0]
        rows = conn.execute("SELECT * FROM evaluations WHERE session_id = ? ORDER BY id ASC LIMIT ? OFFSET ?", (session_id, page_size, offset)).fetchall()
        return {"items": [_decode_row(row) for row in rows], "page": page, "page_size": page_size, "total": total, "has_more": offset + len(rows) < total}


def get_candidate_history(candidate_id: str, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    page, page_size = _clamp_page(page, page_size)
    offset = (page - 1) * page_size
    normalized = normalize_candidate_id(candidate_id)
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) FROM evaluations WHERE candidate_id = ?", (normalized,)).fetchone()[0]
        rows = conn.execute("SELECT * FROM evaluations WHERE candidate_id = ? ORDER BY id ASC LIMIT ? OFFSET ?", (normalized, page_size, offset)).fetchall()
        return {"items": [_decode_row(row) for row in rows], "page": page, "page_size": page_size, "total": total, "has_more": offset + len(rows) < total}


def get_candidate_summary(candidate_id: str) -> dict:
    normalized = normalize_candidate_id(candidate_id)
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        total_answers = conn.execute("SELECT COUNT(*) FROM evaluations WHERE candidate_id = ?", (normalized,)).fetchone()[0]
        if not total_answers:
            return {"candidate_id": normalized, "sessions": [], "total_answers": 0, "recurring_weaknesses": []}
        session_rows = conn.execute(
            """
            SELECT e.session_id, COUNT(*) AS answered, ROUND(AVG(e.score), 1) AS average_score,
                   COALESCE(s.created_at, MIN(e.created_at)) AS started_at
            FROM evaluations e
            LEFT JOIN sessions s ON s.session_id = e.session_id
            WHERE e.candidate_id = ?
            GROUP BY e.session_id, s.created_at
            ORDER BY started_at ASC
            """, (normalized,)
        ).fetchall()
        weakness_rows = conn.execute("SELECT weaknesses FROM evaluations WHERE candidate_id = ?", (normalized,)).fetchall()
    weakness_counts: dict[str, int] = {}
    for row in weakness_rows:
        try:
            weaknesses = json.loads(row[0] or "[]")
        except (json.JSONDecodeError, TypeError):
            weaknesses = []
        for weakness in weaknesses:
            if isinstance(weakness, str):
                weakness_counts[weakness] = weakness_counts.get(weakness, 0) + 1
    recurring = sorted(weakness_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return {
        "candidate_id": normalized,
        "total_answers": total_answers,
        "sessions": [dict(row) for row in session_rows],
        "recurring_weaknesses": [w for w, _ in recurring],
    }
