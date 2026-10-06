from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = Path('/tmp/ai_interview_persistence_test.db')
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ['INTERVIEW_DB_PATH'] = str(TEST_DB)

from fastapi.testclient import TestClient

from interview_engine import (
    InterviewConfig,
    InterviewEngine,
    InterviewType,
    load_interview_state,
    save_interview_state,
)
from main import app
from storage import create_session


def make_state(session_id: str = 'persist-session'):
    state = InterviewEngine().create_session(
        session_id=session_id,
        candidate_id='candidate-1',
        config=InterviewConfig(
            role='Software Engineer',
            interview_type=InterviewType.technical,
            difficulty='medium',
            question_count=2,
        ),
    )
    return state


def test_interview_state_persists_and_restores():
    state = make_state()
    first_id = state.current_question.id

    state.current_index = 1
    state.answered_question_ids.append(first_id)
    save_interview_state(state)

    restored = load_interview_state(state.session_id, state.candidate_id)

    assert restored is not None
    assert restored.current_index == 1
    assert restored.answered_question_ids == [first_id]
    assert restored.current_question is not None
    assert restored.current_question.id != first_id


def test_interview_state_survives_new_engine_instance():
    state = make_state('restart-session')
    save_interview_state(state)

    restored = load_interview_state('restart-session', 'candidate-1')

    assert restored is not None
    assert restored.current_index == 0
    assert restored.current_question is not None
    assert restored.current_question.id == state.current_question.id


def test_interview_next_api_advances_and_persists():
    session_id = 'api-next-session'
    candidate_id = 'api-next-candidate'
    token = create_session(session_id, candidate_id)
    client = TestClient(app)

    start = client.post(
        '/interview/start',
        headers={'X-Session-Token': token},
        json={
            'session_id': session_id,
            'candidate_id': candidate_id,
            'role': 'Software Engineer',
            'interview_type': 'technical',
            'difficulty': 'medium',
            'question_count': 2,
        },
    )
    assert start.status_code == 200
    first_id = start.json()['question']['id']

    next_response = client.post(
        '/interview/next',
        headers={'X-Session-Token': token},
        json={
            'session_id': session_id,
            'candidate_id': candidate_id,
            'question_id': first_id,
        },
    )

    assert next_response.status_code == 200
    data = next_response.json()
    assert data['completed'] is False
    assert data['question']['id'] != first_id
    assert data['question_number'] == 2

    persisted = load_interview_state(session_id, candidate_id)
    assert persisted is not None
    assert persisted.current_index == 1
    assert persisted.answered_question_ids == [first_id]


def test_interview_start_resumes_existing_state():
    session_id = 'resume-session'
    candidate_id = 'resume-candidate'
    token = create_session(session_id, candidate_id)
    client = TestClient(app)

    start_payload = {
        'session_id': session_id,
        'candidate_id': candidate_id,
        'role': 'Software Engineer',
        'interview_type': 'technical',
        'difficulty': 'medium',
        'question_count': 2,
    }

    first = client.post(
        '/interview/start',
        headers={'X-Session-Token': token},
        json=start_payload,
    )
    assert first.status_code == 200
    first_id = first.json()['question']['id']

    advanced = client.post(
        '/interview/next',
        headers={'X-Session-Token': token},
        json={
            'session_id': session_id,
            'candidate_id': candidate_id,
            'question_id': first_id,
        },
    )
    assert advanced.status_code == 200
    second_id = advanced.json()['question']['id']

    resumed = client.post(
        '/interview/start',
        headers={'X-Session-Token': token},
        json=start_payload,
    )

    assert resumed.status_code == 200
    assert resumed.json()['question']['id'] == second_id
    assert resumed.json()['question']['question_number'] == 2


def test_interview_next_rejects_wrong_question():
    session_id = 'wrong-question-session'
    candidate_id = 'wrong-question-candidate'
    token = create_session(session_id, candidate_id)
    client = TestClient(app)

    start = client.post(
        '/interview/start',
        headers={'X-Session-Token': token},
        json={
            'session_id': session_id,
            'candidate_id': candidate_id,
            'role': 'Software Engineer',
            'interview_type': 'technical',
            'difficulty': 'medium',
            'question_count': 2,
        },
    )
    assert start.status_code == 200

    response = client.post(
        '/interview/next',
        headers={'X-Session-Token': token},
        json={
            'session_id': session_id,
            'candidate_id': candidate_id,
            'question_id': 'not-current-question',
        },
    )

    assert response.status_code == 409

    state = load_interview_state(session_id, candidate_id)
    assert state is not None
    assert state.current_index == 0
    assert state.answered_question_ids == []


def test_interview_next_requires_authentication():
    client = TestClient(app)
    response = client.post(
        '/interview/next',
        json={
            'session_id': 'missing-auth',
            'candidate_id': 'candidate',
            'question_id': 'technical-medium-001',
        },
    )
    assert response.status_code == 401
