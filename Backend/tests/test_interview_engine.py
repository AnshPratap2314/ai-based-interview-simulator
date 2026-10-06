import random

import pytest

from interview_engine import (
    InterviewConfig,
    InterviewEngine,
    InterviewType,
)


def test_create_technical_interview():
    engine = InterviewEngine(rng=random.Random(1))

    config = InterviewConfig(
        role="Python Developer",
        interview_type=InterviewType.technical,
        difficulty="medium",
        question_count=2,
    )

    state = engine.create_session(
        session_id="session-1",
        candidate_id="candidate-1",
        config=config,
    )

    assert state.session_id == "session-1"
    assert state.candidate_id == "candidate-1"
    assert len(state.questions) == 2
    assert state.current_question is not None
    assert state.completed is False


def test_questions_match_type_and_difficulty():
    engine = InterviewEngine(rng=random.Random(2))

    config = InterviewConfig(
        role="ML Engineer",
        interview_type=InterviewType.aiml,
        difficulty="hard",
        question_count=2,
    )

    state = engine.create_session(
        session_id="session-2",
        candidate_id="candidate-2",
        config=config,
    )

    assert len(state.questions) == 2

    for question in state.questions:
        assert question.interview_type == InterviewType.aiml
        assert question.difficulty == "hard"


def test_no_duplicate_question_inside_session():
    engine = InterviewEngine(rng=random.Random(3))

    config = InterviewConfig(
        role="Software Engineer",
        interview_type=InterviewType.technical,
        difficulty="medium",
        question_count=2,
    )

    state = engine.create_session(
        session_id="session-3",
        candidate_id="candidate-3",
        config=config,
    )

    ids = [question.id for question in state.questions]

    assert len(ids) == len(set(ids))


def test_previous_questions_are_avoided():
    engine = InterviewEngine(rng=random.Random(4))

    config = InterviewConfig(
        role="Software Engineer",
        interview_type=InterviewType.technical,
        difficulty="easy",
        question_count=1,
    )

    state = engine.create_session(
        session_id="session-4",
        candidate_id="candidate-4",
        config=config,
        previous_question_ids=["technical-easy-001"],
    )

    assert state.questions[0].id != "technical-easy-001"


def test_mark_answered_advances_state():
    engine = InterviewEngine(rng=random.Random(5))

    config = InterviewConfig(
        role="Software Engineer",
        interview_type=InterviewType.technical,
        difficulty="easy",
        question_count=2,
    )

    state = engine.create_session(
        session_id="session-5",
        candidate_id="candidate-5",
        config=config,
    )

    first_question = state.current_question

    engine.mark_answered(state)

    assert first_question is not None
    assert first_question.id in state.answered_question_ids
    assert state.current_index == 1
    assert state.answered_count == 1
    assert state.completed is False


def test_invalid_question_count():
    engine = InterviewEngine()

    config = InterviewConfig(
        role="Software Engineer",
        interview_type=InterviewType.technical,
        difficulty="easy",
        question_count=0,
    )

    with pytest.raises(ValueError):
        engine.create_session(
            session_id="session-6",
            candidate_id="candidate-6",
            config=config,
        )


def test_invalid_interview_type():
    engine = InterviewEngine()

    with pytest.raises(ValueError):
        InterviewConfig(
            role="Software Engineer",
            interview_type="invalid",  # type: ignore[arg-type]
            difficulty="easy",
            question_count=1,
        ).validate()