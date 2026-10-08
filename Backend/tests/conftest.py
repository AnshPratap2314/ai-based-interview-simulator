from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


TEST_DB_PATH = Path(tempfile.gettempdir()) / f"ai_interview_pytest_{os.getpid()}.db"

os.environ["TEST_DB_PATH"] = str(TEST_DB_PATH)
os.environ["INTERVIEW_DB_PATH"] = str(TEST_DB_PATH)


for suffix in ("", "-wal", "-shm"):
    path = Path(f"{TEST_DB_PATH}{suffix}")
    try:
        path.unlink()
    except FileNotFoundError:
        pass


@pytest.fixture(scope="session", autouse=True)
def initialize_test_database(storage=None):
    from storage import init_db

    init_db()

    yield


@pytest.fixture(autouse=True)
def isolate_global_test_state():
    import main

    main._request_times.clear()

    yield

    main._request_times.clear()