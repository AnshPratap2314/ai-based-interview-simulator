from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from adaptive_difficulty import (
    adapt_after_answer,
    choose_next_question,
    decide_next_difficulty,
    recent_average,
)
from interview_engine import (
    InterviewConfig,
    InterviewQuestion,
    InterviewState,
    InterviewType,
)


def _state():
    config = InterviewConfig(
        "ML Engineer",
        InterviewType.technical,
        "medium",
        4,
    )

    return InterviewState(
        session_id="s",
        candidate_id="c",
        config=config,
        questions=[
            InterviewQuestion(
                "q1",
                "Easy",
                InterviewType.technical,
                "easy",
                ("Python",),
            ),
            InterviewQuestion(
                "q2",
                "Medium",
                InterviewType.technical,
                "medium",
                ("SQL",),
            ),
            InterviewQuestion(
                "q3",
                "Hard",
                InterviewType.technical,
                "hard",
                ("ML",),
            ),
            InterviewQuestion(
                "q4",
                "Medium 2",
                InterviewType.technical,
                "medium",
                ("Docker",),
            ),
        ],
    )


def test_recent_average_uses_recent_two_scores():
    assert recent_average([40, 90, 80]) == 85


def test_high_recent_score_increases_difficulty():
    assert decide_next_difficulty("medium", [90, 82]) == "hard"


def test_low_recent_score_decreases_difficulty():
    assert decide_next_difficulty("hard", [55, 60]) == "medium"


def test_middle_recent_score_keeps_difficulty():
    assert decide_next_difficulty("medium", [70, 75]) == "medium"


def test_difficulty_is_clamped_at_boundaries():
    assert decide_next_difficulty("hard", [100, 100]) == "hard"
    assert decide_next_difficulty("easy", [0, 20]) == "easy"


def test_choose_next_question_prefers_target_difficulty():
    state = _state()
    state.current_index = 1

    assert choose_next_question(state, "hard").id == "q3"


def test_adaptive_transition_selects_harder_remaining_question():
    state = _state()

    adapt_after_answer(state, "q1", [90])

    assert state.current_index == 1
    assert state.current_question.id == "q3"
    assert state.answered_question_ids == ["q1"]


def test_adaptive_transition_selects_easier_remaining_question():
    state = _state()
    state.current_index = 2

    adapt_after_answer(state, "q3", [50])

    assert state.current_index == 3
    assert state.current_question.id == "q4"


def test_adaptive_transition_preserves_question_set():
    state = _state()
    original_ids = {question.id for question in state.questions}

    adapt_after_answer(state, "q1", [95])

    assert {question.id for question in state.questions} == original_ids