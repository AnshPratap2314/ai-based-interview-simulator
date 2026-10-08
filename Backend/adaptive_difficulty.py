from __future__ import annotations

from dataclasses import replace

from interview_engine import InterviewQuestion, InterviewState

DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}
UP_THRESHOLD = 85.0
DOWN_THRESHOLD = 60.0
RECENT_SCORE_WINDOW = 2


def normalize_difficulty(value: str) -> str:
    difficulty = str(value).strip().lower()
    if difficulty not in DIFFICULTY_ORDER:
        raise ValueError("Difficulty must be easy, medium, or hard.")
    return difficulty


def recent_average(scores: list[float] | tuple[float, ...]) -> float | None:
    if not scores:
        return None
    recent = [float(score) for score in scores[-RECENT_SCORE_WINDOW:]]
    return sum(recent) / len(recent)


def decide_next_difficulty(
    current_difficulty: str,
    recent_scores: list[float] | tuple[float, ...],
) -> str:
    current = normalize_difficulty(current_difficulty)
    average = recent_average(recent_scores)
    if average is None:
        return current

    level = DIFFICULTY_ORDER[current]
    if average >= UP_THRESHOLD:
        return ["easy", "medium", "hard"][min(level + 1, 2)]
    if average <= DOWN_THRESHOLD:
        return ["easy", "medium", "hard"][max(level - 1, 0)]
    return current


def _difficulty_distance(question: InterviewQuestion, target: str) -> int:
    return abs(DIFFICULTY_ORDER[normalize_difficulty(question.difficulty)] - DIFFICULTY_ORDER[target])


def choose_next_question(
    state: InterviewState,
    target_difficulty: str,
) -> InterviewQuestion | None:
    target = normalize_difficulty(target_difficulty)
    remaining = state.questions[state.current_index:]
    if not remaining:
        return None

    return min(
        enumerate(remaining),
        key=lambda item: (_difficulty_distance(item[1], target), item[0]),
    )[1]


def adapt_after_answer(
    state: InterviewState,
    question_id: str,
    recent_scores: list[float] | tuple[float, ...],
) -> InterviewState:
    current = state.current_question
    if current is None:
        raise ValueError("Interview is already completed.")
    if current.id != question_id:
        raise ValueError("The answered question does not match the current question.")
    if question_id in state.answered_question_ids:
        raise ValueError("This question has already been answered.")

    state.answered_question_ids.append(current.id)
    state.current_index += 1

    if state.completed:
        return state

    target = decide_next_difficulty(state.config.difficulty, recent_scores)
    next_question = choose_next_question(state, target)
    if next_question is None:
        return state

    remaining = state.questions[state.current_index:]
    state.questions[state.current_index:] = [
        next_question,
        *[question for question in remaining if question.id != next_question.id],
    ]
    return state
