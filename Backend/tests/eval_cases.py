"""
8-12 test cases for the /evaluate endpoint.

Each case is a dict with:
  name              - short identifier, shown in test output
  role, difficulty  - sent to the API as-is
  job_description   - optional, "" if not relevant to this case
  question, answer  - the interview Q&A being evaluated
  expect_error      - if set, we expect this HTTP status code and skip all other checks
  expect_min_score / expect_max_score - bounds on the returned `score` (0-100)
  expect_human_review - bool, whether needs_human_review should be True or False

Keep this file free of secrets or real candidate data - it's meant to be committed.
"""

CASES = [
    # --- representative: clear strong answer ---
    {
        "name": "strong_technical_answer",
        "role": "Backend Developer",
        "difficulty": "medium",
        "job_description": "",
        "question": "What is the difference between let, const and var?",
        "answer": (
            "var is function-scoped and hoisted with an initial value of undefined. "
            "let and const are block-scoped and live in the temporal dead zone until "
            "their declaration runs. const additionally prevents reassignment of the "
            "binding, though it does not make objects or arrays immutable."
        ),
        "expect_min_score": 70,
        "expect_human_review": False,
    },

    # --- representative: clear weak-but-relevant answer ---
    {
        "name": "weak_but_relevant_answer",
        "role": "Backend Developer",
        "difficulty": "easy",
        "job_description": "",
        "question": "What is a variable?",
        "answer": "A variable stores a value so you can use it later in the code.",
        "expect_min_score": 40,
        "expect_max_score": 85,
        "expect_human_review": False,
    },

    # --- edge: completely off-topic ---
    {
        "name": "off_topic_answer",
        "role": "Backend Developer",
        "difficulty": "medium",
        "job_description": "",
        "question": "Explain REST API.",
        "answer": "I like pizza and going for long walks on weekends.",
        "expect_max_score": 20,
        "expect_human_review": True,
    },

    # --- edge: confident but factually wrong (the hard case) ---
    {
        "name": "confident_but_wrong",
        "role": "Backend Developer",
        "difficulty": "hard",
        "job_description": "",
        "question": "Explain ACID properties in DBMS.",
        "answer": (
            "ACID stands for Atomicity, Consistency, Integration, and Durability. "
            "Integration means all related tables must be joined together before "
            "a transaction can commit."
        ),
        "expect_max_score": 55,
        "expect_human_review": False,
    },

    # --- edge: extremely short, low-effort ---
    {
        "name": "one_word_answer",
        "role": "HR",
        "difficulty": "easy",
        "job_description": "",
        "question": "Tell me about yourself.",
        "answer": "Good.",
        "expect_max_score": 20,
        "expect_human_review": True,
    },

    # --- edge: verbose but vague, no real content ---
    {
        "name": "verbose_but_vague",
        "role": "AI Engineer",
        "difficulty": "medium",
        "job_description": "",
        "question": "Explain gradient descent.",
        "answer": (
            "Gradient descent is a really important and widely used concept in "
            "machine learning that helps models learn better over time by making "
            "adjustments repeatedly until things improve and the model becomes "
            "more accurate and useful for real-world tasks."
        ),
        "expect_max_score": 50,
        "expect_human_review": False,
    },

    # --- edge: job description changes what "good" means ---
    {
        "name": "role_aware_with_job_description",
        "role": "Senior AI Engineer",
        "difficulty": "hard",
        "job_description": (
            "We need someone who can explain tradeoffs precisely to non-technical "
            "stakeholders and justify model choices with concrete metrics."
        ),
        "question": "Explain precision, recall and F1-score.",
        "answer": (
            "Precision is the fraction of positive predictions that are correct. "
            "Recall is the fraction of actual positives the model catches. F1 is "
            "their harmonic mean, used when you need one number that balances both, "
            "e.g. in fraud detection where both false positives and false negatives "
            "are costly for different business reasons."
        ),
        "expect_min_score": 75,
        "expect_human_review": False,
    },

    # --- edge: partially correct, missing key concept ---
    # Note: this is a genuinely borderline case. A bare-minimum answer to a "hard"
    # question can reasonably be flagged for human review even when it's confidently
    # scored - we don't assert needs_human_review here since either True or False
    # is a defensible outcome, and asserting one would be testing our own guess
    # rather than a real requirement.
    {
        "name": "partially_correct_missing_key_concept",
        "role": "Backend Developer",
        "difficulty": "hard",
        "job_description": "",
        "question": "Explain database indexing and its advantages.",
        "answer": (
            "An index makes lookups faster because the database doesn't have to "
            "scan every row."
        ),
        "expect_min_score": 30,
        "expect_max_score": 70,
    },

    # --- edge: non-English input ---
    {
        "name": "non_english_input",
        "role": "Backend Developer",
        "difficulty": "easy",
        "job_description": "",
        "question": "What is an API?",
        "answer": "Une API est une interface qui permet a deux logiciels de communiquer entre eux.",
        "expect_human_review": True,
    },

    # --- edge: garbled / fragmented formatting ---
    {
        "name": "garbled_formatting",
        "role": "AI Engineer",
        "difficulty": "hard",
        "job_description": "",
        "question": "Explain bias and variance.",
        "answer": "Var(X) = E(X^2) - [E(X)]^2 bias hi variance low ... underfit? overfit?? idk",
        "expect_max_score": 45,
        "expect_human_review": True,
    },

    # --- failure: empty answer should be rejected before hitting the model ---
    {
        "name": "empty_answer_rejected",
        "role": "Backend Developer",
        "difficulty": "easy",
        "job_description": "",
        "question": "What is a variable?",
        "answer": "   ",
        "expect_error": 400,
    },

    # --- failure: empty question should be rejected before hitting the model ---
    {
        "name": "empty_question_rejected",
        "role": "Backend Developer",
        "difficulty": "easy",
        "job_description": "",
        "question": "   ",
        "answer": "A variable stores a value.",
        "expect_error": 400,
    },
]