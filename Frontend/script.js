const configuredApiUrl = typeof window.APP_API_URL === "string" ? window.APP_API_URL.trim() : "";
const API_URL = (
    configuredApiUrl ||
    (window.location.protocol === "file:" ? "http://127.0.0.1:8000" : window.location.origin)
).replace(/\/$/, "");

console.log("AI Interview Simulator Frontend v3.0.0");

let sessionAccessToken = sessionStorage.getItem("interviewSessionToken") || "";
let candidateAccessToken = localStorage.getItem("interviewCandidateToken") || "";
let storedCandidateId = localStorage.getItem("interviewCandidate") || "";

const questionBanks = {
    technical: {
        easy: [
            "What is OOP?",
            "What is DBMS?",
            "What is JavaScript?",
            "Explain HTML.",
            "What is CSS?",
            "What is a variable?",
            "What is a function?",
            "What is an array?",
            "What is a database?",
            "What is an API?"
        ],

        medium: [
            "Explain the four pillars of OOP.",
            "What is normalization in DBMS?",
            "What is the difference between let, const and var?",
            "What is the difference between HTML and HTML5?",
            "Explain CSS Flexbox and Grid.",
            "What is a primary key and foreign key?",
            "What is exception handling?",
            "What is inheritance?",
            "What is REST API?",
            "Explain the difference between GET and POST."
        ],

        hard: [
            "Explain polymorphism with a practical example.",
            "Explain database indexing and its advantages.",
            "Explain JavaScript closures.",
            "Explain event delegation in JavaScript.",
            "Explain ACID properties in DBMS.",
            "What are database transactions and isolation levels?",
            "Explain process vs thread.",
            "Explain time and space complexity.",
            "Explain RESTful API architecture.",
            "Explain authentication vs authorization."
        ]
    },

    hr: {
        easy: [
            "Tell me about yourself.",
            "What are your strengths?",
            "What are your weaknesses?",
            "Why should we hire you?",
            "Where do you see yourself in five years?",
            "Why do you want this job?",
            "Tell me about your education.",
            "What motivates you?",
            "How do you handle pressure?",
            "What are your career goals?"
        ],

        medium: [
            "Tell me about a challenging project you worked on.",
            "Describe a time you solved a difficult problem.",
            "How do you handle failure?",
            "Describe a situation where you worked in a team.",
            "How do you manage deadlines?",
            "Tell me about a conflict you handled.",
            "How do you prioritize multiple tasks?",
            "Describe a time you took initiative.",
            "What makes you different from other candidates?",
            "How do you handle criticism?"
        ],

        hard: [
            "Tell me about your biggest professional failure and what you learned.",
            "Describe a situation where you disagreed with your manager.",
            "How would you handle an unethical request from a senior?",
            "Tell me about a time you made a decision with incomplete information.",
            "How would you handle failure on an important project?",
            "Describe a situation where you had to convince others.",
            "How would you respond if you received negative feedback unfairly?",
            "Tell me about a time you demonstrated leadership.",
            "What would you do if your team member was not contributing?",
            "Why should we choose you over a more experienced candidate?"
        ]
    },

    aiml: {
        easy: [
            "What is Artificial Intelligence?",
            "What is Machine Learning?",
            "What is supervised learning?",
            "What is unsupervised learning?",
            "What is a dataset?",
            "What is a feature?",
            "What is a machine learning model?",
            "What is classification?",
            "What is regression?",
            "What is overfitting?"
        ],

        medium: [
            "Explain the difference between supervised and unsupervised learning.",
            "Explain bias and variance.",
            "What is cross-validation?",
            "Explain precision, recall and F1-score.",
            "What is feature engineering?",
            "Explain gradient descent.",
            "What is the difference between classification and regression?",
            "Explain decision trees.",
            "What is a neural network?",
            "What is regularization?"
        ],

        hard: [
            "Explain the bias-variance tradeoff in detail.",
            "Explain how backpropagation works.",
            "Compare CNNs, RNNs and Transformers.",
            "Explain gradient descent and its variants.",
            "How would you handle severe class imbalance?",
            "Explain precision-recall tradeoff and when it matters.",
            "How would you detect and prevent data leakage?",
            "Explain overfitting and different techniques to prevent it.",
            "How would you design an end-to-end ML system?",
            "Explain model deployment and monitoring in production."
        ]
    }
};


/* ============================================================
   GLOBAL INTERVIEW STATE
   ============================================================ */

let questions = [];
let currentQuestion = 0;
let totalQuestions = 5;
let interviewScores = [];
let currentEvaluationId = "";

/*
 * IMPORTANT:
 * sessionId represents ONE interview sitting.
 *
 * A NEW sessionId is generated every time Start Interview
 * is clicked.
 */
let sessionId = "";

let candidateId = "";
let interviewContext = {};


/* ============================================================
   UI HELPERS
   ============================================================ */

function initAvatar() {
    const nameField = document.getElementById("candidateId");
    const avatar = document.getElementById("avatar");

    if (!nameField || !avatar) return;

    function updateAvatar() {
        const value = nameField.value.trim();

        if (!value) {
            avatar.textContent = "?";
            return;
        }

        const parts = value.split(/\s+/).filter(Boolean);

        const initials =
            parts.length >= 2
                ? parts[0][0] + parts[1][0]
                : value.slice(0, 2);

        avatar.textContent = initials.toUpperCase();
    }

    nameField.addEventListener("input", () => {
        updateAvatar();
        updateProgress();
    });

    updateAvatar();
}


function initCharCount() {
    const jd = document.getElementById("jobDescription");
    const counter = document.getElementById("jdCharCount");

    if (!jd || !counter) return;

    function update() {
        counter.textContent = `${jd.value.length} / 10,000`;
    }

    jd.addEventListener("input", update);

    update();
}


function initOptionCards() {
    document
        .querySelectorAll(".option-card, .segment")
        .forEach((el) => {

            el.addEventListener("click", () => {

                const targetId =
                    el.getAttribute("data-target");

                const value =
                    el.getAttribute("data-value");

                const hiddenSelect =
                    document.getElementById(targetId);

                if (!hiddenSelect) return;

                hiddenSelect.value = value;

                const group =
                    el.closest(".option-cards, .segmented");

                if (group) {

                    group
                        .querySelectorAll(
                            ".option-card, .segment"
                        )
                        .forEach((sibling) => {

                            sibling.classList.remove("active");

                            sibling.setAttribute(
                                "aria-pressed",
                                "false"
                            );
                        });
                }

                el.classList.add("active");

                el.setAttribute(
                    "aria-pressed",
                    "true"
                );

                updateProgress();
            });
        });
}


function syncOptionCardsFromSelects() {

    [
        "interviewType",
        "difficulty",
        "questionCount"
    ].forEach((id) => {

        const select =
            document.getElementById(id);

        if (!select) return;

        document
            .querySelectorAll(
                `[data-target="${id}"]`
            )
            .forEach((el) => {

                const isActive =
                    el.getAttribute("data-value") ===
                    select.value;

                el.classList.toggle(
                    "active",
                    isActive
                );

                el.setAttribute(
                    "aria-pressed",
                    isActive
                        ? "true"
                        : "false"
                );
            });
    });
}


function updateProgress() {

    const indicator =
        document.getElementById(
            "progressIndicator"
        );

    if (!indicator) return;

    const nameField =
        document.getElementById("candidateId");

    const roleField =
        document.getElementById("role");

    const nameFilled =
        nameField &&
        nameField.value.trim().length > 0;

    const roleFilled =
        roleField &&
        roleField.value.trim().length > 0;

    const setupDone = true;

    const steps =
        indicator.querySelectorAll(
            ".progress-step"
        );

    const states = [
        true,
        nameFilled,
        roleFilled,
        setupDone
    ];

    steps.forEach((step, i) => {

        step.classList.toggle(
            "active",
            Boolean(states[i])
        );
    });
}


function initRoleField() {

    const roleField =
        document.getElementById("role");

    if (!roleField) return;

    roleField.addEventListener(
        "input",
        updateProgress
    );
}


/* ============================================================
   LOCAL STORAGE
   ============================================================ */

function prefillSavedFields() {

    const rememberedRole =
        localStorage.getItem("lastRole");

    const roleField =
        document.getElementById("role");

    if (
        rememberedRole &&
        roleField
    ) {
        roleField.value =
            rememberedRole;
    }
}


/* ============================================================
   PAGE INITIALIZATION
   ============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        prefillSavedFields();

        initAvatar();

        initCharCount();

        initOptionCards();

        initRoleField();

        syncOptionCardsFromSelects();

        updateProgress();
    }
);


/* ============================================================
   QUESTION MANAGEMENT
   ============================================================ */

/*
 * Returns a unique storage key for this user's
 * question history.
 */
function getQuestionHistoryKey(
    candidate,
    type,
    difficulty
) {

    return (
        `usedInterviewQuestions:` +
        `${candidate}:` +
        `${type}:` +
        `${difficulty}`
    );
}


/*
 * Get previously used questions.
 */
function getUsedQuestions(
    candidate,
    type,
    difficulty
) {

    const key =
        getQuestionHistoryKey(
            candidate,
            type,
            difficulty
        );

    try {

        const stored =
            localStorage.getItem(key);

        if (!stored) return [];

        const parsed =
            JSON.parse(stored);

        return Array.isArray(parsed)
            ? parsed
            : [];

    } catch (error) {

        console.warn(
            "Unable to read question history:",
            error
        );

        return [];
    }
}


/*
 * Save used questions.
 */
function saveUsedQuestions(
    candidate,
    type,
    difficulty,
    usedQuestions
) {

    const key =
        getQuestionHistoryKey(
            candidate,
            type,
            difficulty
        );

    try {

        localStorage.setItem(
            key,
            JSON.stringify(
                [...new Set(usedQuestions)]
            )
        );

    } catch (error) {

        console.warn(
            "Unable to save question history:",
            error
        );
    }
}


/*
 * Select questions while avoiding questions
 * from previous interviews.
 */
function selectInterviewQuestions(
    candidate,
    type,
    difficulty,
    count
) {

    const bank =
        questionBanks?.[type]?.[difficulty] || [];

    if (!bank.length) {

        throw new Error(
            "No questions are available for this interview configuration."
        );
    }

    let usedQuestions =
        getUsedQuestions(
            candidate,
            type,
            difficulty
        );

    let availableQuestions =
        bank.filter(
            question =>
                !usedQuestions.includes(question)
        );


    /*
     * If there are not enough unused questions,
     * use the remaining questions first.
     *
     * Only reset the history when the entire
     * question bank has effectively been used.
     */
    if (
        availableQuestions.length < count
    ) {

        /*
         * Use all remaining questions first.
         */
        const remaining =
            [...availableQuestions];

        /*
         * Then, if necessary, reset the bank
         * and fill the remaining slots.
         */
        if (
            remaining.length < count
        ) {

            usedQuestions = [];

            availableQuestions =
                [...bank];
        }
    }


    /*
     * Shuffle without modifying the original bank.
     */
    const shuffled =
        [...availableQuestions]
            .sort(
                () => Math.random() - 0.5
            );


    /*
     * Select requested number.
     */
    const selected =
        shuffled.slice(
            0,
            Math.min(
                count,
                shuffled.length
            )
        );


    /*
     * If we still need more questions,
     * fill from the complete bank without
     * duplicates inside the same interview.
     */
    if (
        selected.length < count
    ) {

        const alreadySelected =
            new Set(selected);

        const fallback =
            [...bank]
                .sort(
                    () => Math.random() - 0.5
                )
                .filter(
                    q => !alreadySelected.has(q)
                );

        for (
            const question of fallback
        ) {

            if (
                selected.length >= count
            ) {
                break;
            }

            selected.push(question);
        }
    }


    /*
     * Store selected questions as used.
     */
    saveUsedQuestions(
        candidate,
        type,
        difficulty,
        [
            ...usedQuestions,
            ...selected
        ]
    );

    return selected;
}


/* ============================================================
   START INTERVIEW
   ============================================================ */

async function startInterview() {

    const type =
        document.getElementById(
            "interviewType"
        ).value;

    const difficulty =
        document.getElementById(
            "difficulty"
        ).value;

    totalQuestions =
        parseInt(
            document.getElementById(
                "questionCount"
            ).value,
            10
        );


    const rawCandidateId =
        document.getElementById(
            "candidateId"
        ).value.trim();

    candidateId =
        rawCandidateId ||
        `guest-${Date.now()}`;


    const rawRole =
        document.getElementById(
            "role"
        ).value.trim() ||
        "Software Developer";

    localStorage.setItem(
        "lastRole",
        rawRole
    );


    /*
     * ========================================================
     * IMPORTANT FIX
     *
     * Generate a completely NEW session ID
     * every time the user starts an interview.
     * ========================================================
     */

    sessionId =
        typeof crypto !== "undefined" &&
        typeof crypto.randomUUID === "function"
            ? crypto.randomUUID()
            : `session-${Date.now()}-${Math.random()
                  .toString(36)
                  .slice(2)}`;


    interviewContext = {

        role: rawRole,

        jobDescription:
            document
                .getElementById(
                    "jobDescription"
                )
                .value.trim(),

        type,

        difficulty
    };


    /*
     * Reset interview state.
     */
    currentQuestion = 0;

    interviewScores = [];

    questions = [];


    /*
     * Authorize the new session.
     */
    try {

        const sessionResponse =
            await fetch(
                `${API_URL}/session/start`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        session_id:
                            sessionId,

                        candidate_id:
                            candidateId,

                        /*
                         * Existing token allows the same
                         * candidate to start another session.
                         */
                        ...(candidateAccessToken
                            ? {
                                access_token:
                                    candidateAccessToken
                            }
                            : {})
                    })
                }
            );


        const sessionPayload =
            await sessionResponse
                .json()
                .catch(() => ({}));


        if (!sessionResponse.ok) {

            throw new Error(
                sessionPayload.detail ||
                `Unable to authorize interview session (${sessionResponse.status}).`
            );
        }


        if (
            typeof sessionPayload.session_token !== "string" ||
            !sessionPayload.session_token ||
            typeof sessionPayload.candidate_access_token !== "string" ||
            !sessionPayload.candidate_access_token ||
            typeof sessionPayload.candidate_id !== "string" ||
            !sessionPayload.candidate_id
        ) {
            throw new Error("Backend returned an invalid session response.");
        }

        sessionAccessToken = sessionPayload.session_token;
        candidateAccessToken = sessionPayload.candidate_access_token;
        candidateId = sessionPayload.candidate_id;
        storedCandidateId = candidateId;

        sessionStorage.setItem("interviewSessionToken", sessionAccessToken);
        localStorage.setItem("interviewCandidateToken", candidateAccessToken);
        localStorage.setItem("interviewCandidate", candidateId);


    } catch (error) {

        console.error(
            "Session start error:",
            error
        );

        alert(
            error.message ||
            "Unable to start the interview."
        );

        return;
    }


    /*
     * ========================================================
     * Select unique questions.
     * ========================================================
     */

    try {

        questions =
            selectInterviewQuestions(
                candidateId,
                type,
                difficulty,
                totalQuestions
            );

    } catch (error) {

        console.error(
            "Question selection error:",
            error
        );

        alert(
            error.message ||
            "Unable to load interview questions."
        );

        return;
    }


    if (!questions.length) {

        alert(
            "No interview questions are available."
        );

        return;
    }


    /*
     * Make sure totalQuestions matches
     * the actual number available.
     */
    totalQuestions =
        questions.length;


    /*
     * Switch from setup to interview.
     */

    const setup =
        document.getElementById(
            "setup"
        );

    const interview =
        document.getElementById(
            "interview"
        );


    if (setup) {
        setup.style.display = "none";
    }

    if (interview) {
        interview.style.display = "block";
    }


    showQuestion();
}


/* ============================================================
   SHOW QUESTION
   ============================================================ */

function showQuestion() {

    const questionElement =
        document.getElementById(
            "question"
        );

    const answerElement =
        document.getElementById(
            "answer"
        );

    const resultElement =
        document.getElementById(
            "result"
        );

    const submitButton =
        document.getElementById(
            "submitButton"
        );

    const nextButton =
        document.getElementById(
            "nextButton"
        );


    if (
        !questionElement ||
        !answerElement ||
        !resultElement
    ) {
        console.error(
            "Required interview UI elements are missing."
        );

        return;
    }


    const current =
        questions[currentQuestion];


    if (!current) {

        console.error(
            "Question does not exist:",
            currentQuestion
        );

        return;
    }


    questionElement.innerText =
        `Question ${currentQuestion + 1}/${totalQuestions}: ${current}`;


    answerElement.value = "";

    resultElement.innerHTML = "";


    if (submitButton) {

        submitButton.style.display = "";

        submitButton.disabled = false;

        submitButton.innerText =
            "Submit Answer";
    }


    if (nextButton) {

        nextButton.style.display = "none";
    currentEvaluationId = (globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : `evaluation-${Date.now()}-${Math.random().toString(36).slice(2)}`);

        nextButton.disabled = false;

        nextButton.innerText =
            currentQuestion ===
            totalQuestions - 1
                ? "Finish Interview"
                : "Next Question";
    }


    /*
     * Focus answer box for better UX.
     */
    setTimeout(() => {

        try {
            answerElement.focus();
        } catch {
            // Ignore focus errors.
        }

    }, 50);
}


/* ============================================================
   HTML SECURITY
   ============================================================ */

function escapeHtml(value) {

    return String(
        value ?? ""
    ).replace(
        /[&<>'"]/g,
        char =>
            ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                "'": "&#39;",
                '"': "&quot;"
            })[char]
    );
}


function listHtml(items) {

    if (!Array.isArray(items)) {

        if (
            items === null ||
            items === undefined ||
            items === ""
        ) {
            return "<ul><li>None provided.</li></ul>";
        }

        items = [items];
    }


    if (!items.length) {

        return "<ul><li>None provided.</li></ul>";
    }


    return `
        <ul>
            ${items
                .map(
                    item =>
                        `<li>${escapeHtml(item)}</li>`
                )
                .join("")}
        </ul>
    `;
}


/* ============================================================
   EVALUATION
   ============================================================ */

async function checkAnswer() {

    const answerElement =
        document.getElementById(
            "answer"
        );

    const result =
        document.getElementById(
            "result"
        );

    const submitButton =
        document.getElementById(
            "submitButton"
        );

    const nextButton =
        document.getElementById(
            "nextButton"
        );


    if (
        !answerElement ||
        !result
    ) {

        console.error(
            "Evaluation UI elements are missing."
        );

        return;
    }


    const answer =
        answerElement.value.trim();

    const question =
        questions[currentQuestion];


    if (!question) {

        result.innerHTML = `
            <p>
                <strong>
                    ❌ No active question found.
                </strong>
            </p>
        `;

        return;
    }


    if (!answer) {

        result.innerHTML = `
            <p>
                <strong>
                    Please enter your answer first.
                </strong>
            </p>
        `;

        answerElement.focus();

        return;
    }


    if (!sessionAccessToken) {

        result.innerHTML = `
            <p>
                <strong>
                    ❌ Your interview session has expired.
                </strong>
            </p>

            <p>
                Please start the interview again.
            </p>
        `;

        return;
    }


    /*
     * Prevent multiple requests.
     */
    if (
        submitButton &&
        submitButton.disabled
    ) {
        return;
    }


    result.innerHTML = `
        <div class="evaluation-loading">
            <strong>
                🤖 AI is evaluating your answer...
            </strong>

            <p>
                Gemini is analyzing accuracy,
                relevance, clarity and completeness.
            </p>
        </div>
    `;


    if (submitButton) {

        submitButton.disabled = true;

        submitButton.innerText =
            "Evaluating...";
    }


    try {

        console.log(
            "Sending evaluation request:",
            {
                API_URL,
                sessionId,
                candidateId,
                question
            }
        );


        const response =
            await fetch(
                `${API_URL}/evaluate`,
                {
                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json",

                        "X-Session-Token":
                            sessionAccessToken,
                        "X-Evaluation-Id":
                            currentEvaluationId
                    },

                    body: JSON.stringify({

                        session_id:
                            sessionId,

                        candidate_id:
                            candidateId,

                        role:
                            interviewContext.role,

                        difficulty:
                            interviewContext.difficulty,

                        job_description:
                            interviewContext.jobDescription,

                        question,

                        answer,

                        expected_skills: []
                    })
                }
            );


        const payload =
            await response
                .json()
                .catch(() => ({}));


        console.log(
            "AI evaluation response:",
            payload
        );


        /*
         * Handle backend errors.
         */
        if (!response.ok) {

            throw new Error(
                payload.detail ||
                `Evaluation failed with HTTP ${response.status}.`
            );
        }


        /*
         * Make sure Gemini actually returned
         * a usable evaluation.
         */
        if (
            typeof payload.score !== "number"
        ) {

            throw new Error(
                "The AI backend returned an invalid evaluation. No valid score was received."
            );
        }


        /*
         * Normalize confidence.
         *
         * Backend normally returns 0.95.
         * If it returns 95, convert to 0.95.
         */
        let confidence =
            Number(payload.confidence);


        if (!Number.isFinite(confidence)) {

            confidence = null;

        } else if (
            confidence > 1 &&
            confidence <= 100
        ) {

            confidence =
                confidence / 100;
        }


        /*
         * Store evaluation.
         */
        interviewScores.push({

            ...payload,

            confidence
        });


        /*
         * Render evaluation.
         */

        const confidenceText =
            confidence === null
                ? "N/A"
                : `${Math.round(
                    confidence * 100
                )}%`;


        const reviewText =
            payload.needs_human_review
                ? `
                    <div class="review-warning">
                        <strong>
                            ⚠️ Human Review Recommended
                        </strong>

                        <p>
                            This evaluation may contain
                            ambiguity or lower confidence.
                        </p>
                    </div>
                `
                : "";


        result.innerHTML = `

            <div class="evaluation-result">

                <h3>
                    Overall Score:
                    ${escapeHtml(
                        payload.score
                    )}/100
                </h3>


                <p>
                    <strong>
                        Technical Accuracy:
                    </strong>

                    ${escapeHtml(
                        payload.technical_accuracy
                    )}/10
                </p>


                <p>
                    <strong>
                        Relevance:
                    </strong>

                    ${escapeHtml(
                        payload.relevance
                    )}/10
                </p>


                <p>
                    <strong>
                        Clarity:
                    </strong>

                    ${escapeHtml(
                        payload.clarity
                    )}/10
                </p>


                <p>
                    <strong>
                        Completeness:
                    </strong>

                    ${escapeHtml(
                        payload.completeness
                    )}/10
                </p>


                <p>
                    <strong>
                        Confidence:
                    </strong>

                    ${confidenceText}
                </p>


                ${reviewText}


                <h4>
                    💪 Strengths
                </h4>

                ${listHtml(
                    payload.strengths
                )}


                <h4>
                    ⚠️ Weaknesses
                </h4>

                ${listHtml(
                    payload.weaknesses
                )}


                <h4>
                    🔎 Evidence
                </h4>

                ${listHtml(
                    payload.evidence
                )}


                <h4>
                    💡 Feedback
                </h4>

                <p>
                    ${escapeHtml(
                        payload.feedback
                    )}
                </p>


                <h4>
                    ✨ Improved Answer
                </h4>

                <p>
                    ${escapeHtml(
                        payload.improved_answer
                    )}
                </p>


                ${
                    Array.isArray(
                        payload.skills_assessed
                    ) &&
                    payload.skills_assessed.length
                        ? `
                            <h4>
                                🎯 Skills Assessed
                            </h4>

                            ${listHtml(
                                payload.skills_assessed.map(
                                    skill =>
                                        `${skill.skill}: ${skill.score}/10`
                                )
                            )}
                        `
                        : ""
                }

            </div>
        `;


        /*
         * Successfully evaluated.
         */
        if (submitButton) {

            submitButton.style.display =
                "none";

            submitButton.disabled = true;
        }


        if (nextButton) {

            nextButton.style.display =
                "";

            nextButton.disabled =
                false;
        }


    } catch (error) {

        console.error(
            "Evaluation error:",
            error
        );


        result.innerHTML = `

            <div class="evaluation-error">

                <h3>
                    ❌ Evaluation Failed
                </h3>

                <p>
                    ${escapeHtml(
                        error.message ||
                        "Unable to evaluate your answer."
                    )}
                </p>

                <p>
                    Please try submitting
                    your answer again.
                </p>

            </div>
        `;


        if (submitButton) {

            submitButton.disabled =
                false;

            submitButton.innerText =
                "Submit Answer";
        }


        if (nextButton) {

            nextButton.style.display =
                "none";
        }
    }
}


/* ============================================================
   NEXT QUESTION
   ============================================================ */

function nextQuestion() {

    /*
     * Do not allow next question until
     * current answer has been evaluated.
     */
    if (
        interviewScores.length !==
        currentQuestion + 1
    ) {

        const result =
            document.getElementById(
                "result"
            );

        if (result) {

            result.innerHTML += `
                <p>
                    <strong>
                        Please submit your answer
                        and wait for the AI evaluation
                        before continuing.
                    </strong>
                </p>
            `;
        }

        return;
    }


    if (
        currentQuestion ===
        totalQuestions - 1
    ) {

        finishInterview();

        return;
    }


    currentQuestion++;

    showQuestion();
}


/* ============================================================
   FINISH INTERVIEW
   ============================================================ */

async function finishInterview() {

    if (!interviewScores.length) {

        alert(
            "No evaluated answers were found."
        );

        return;
    }


    /*
     * Only count successfully evaluated
     * questions.
     */
    const validScores =
        interviewScores.filter(
            item =>
                typeof item.score ===
                "number"
        );


    if (!validScores.length) {

        alert(
            "No valid AI evaluations were found."
        );

        return;
    }


    const averageScore =
        Math.round(
            validScores.reduce(
                (sum, item) =>
                    sum +
                    Number(
                        item.score || 0
                    ),
                0
            ) /
            validScores.length
        );


    const technicalAccuracy =
        average(
            validScores.map(
                item =>
                    Number(
                        item.technical_accuracy ||
                        0
                    )
            )
        );


    const relevance =
        average(
            validScores.map(
                item =>
                    Number(
                        item.relevance ||
                        0
                    )
            )
        );


    const clarity =
        average(
            validScores.map(
                item =>
                    Number(
                        item.clarity ||
                        0
                    )
            )
        );


    const completeness =
        average(
            validScores.map(
                item =>
                    Number(
                        item.completeness ||
                        0
                    )
            )
        );


    const allWeaknesses =
        [
            ...new Set(
                validScores.flatMap(
                    item =>
                        Array.isArray(
                            item.weaknesses
                        )
                            ? item.weaknesses
                            : []
                )
            )
        ];


    /*
     * Performance label.
     */
    let performance =
        "Needs Improvement";


    if (averageScore >= 85) {

        performance =
            "Excellent";

    } else if (averageScore >= 70) {

        performance =
            "Good";

    } else if (averageScore >= 50) {

        performance =
            "Average";
    }


    /*
     * Candidate history.
     */
    let trendHtml =
        "<p>This is your first recorded session.</p>";


    try {

        const summaryResponse =
            await fetch(
                `${API_URL}/history/candidate/` +
                `${encodeURIComponent(
                    candidateId
                )}/summary`,
                {
                    headers: {
                        "X-Session-Token":
                            candidateAccessToken
                    }
                }
            );


        if (summaryResponse.ok) {

            const summary =
                await summaryResponse
                    .json();


            if (
                summary.sessions &&
                summary.sessions.length > 1
            ) {

                const rows =
                    summary.sessions
                        .map(
                            (s, i) =>
                                `
                                <li>
                                    Session ${
                                        i + 1
                                    }:
                                    avg ${
                                        s.average_score
                                    }/100
                                    (
                                    ${
                                        s.answered
                                    }
                                    answered
                                    )
                                    -
                                    ${
                                        escapeHtml(
                                            s.started_at
                                        )
                                    }
                                </li>
                                `
                        )
                        .join("");


                trendHtml = `

                    <p>
                        You've completed
                        <strong>
                            ${
                                summary.sessions.length
                            }
                            sessions
                        </strong>
                        under this profile.
                    </p>

                    <ul>
                        ${rows}
                    </ul>

                    <p>
                        <strong>
                            Recurring weaknesses
                            across sessions:
                        </strong>
                    </p>

                    ${listHtml(
                        summary.recurring_weaknesses
                    )}

                `;
            }
        }

    } catch (error) {

        console.error(
            "Could not load candidate trend:",
            error
        );
    }


    /*
     * Final report.
     */
    const interview =
        document.getElementById(
            "interview"
        );


    if (!interview) return;


    interview.innerHTML = `

        <h1>
            Interview Report
        </h1>


        <div class="question-container">

            <p>
                <strong>
                    Role:
                </strong>

                ${escapeHtml(
                    interviewContext.role
                )}
            </p>


            <p>
                <strong>
                    Interview Type:
                </strong>

                ${escapeHtml(
                    interviewContext.type
                )}
            </p>


            <p>
                <strong>
                    Difficulty:
                </strong>

                ${escapeHtml(
                    interviewContext.difficulty
                )}
            </p>


            <p>
                <strong>
                    Overall Score:
                </strong>

                ${averageScore}/100
            </p>


            <p>
                <strong>
                    Questions Completed:
                </strong>

                ${
                    validScores.length
                }/${totalQuestions}
            </p>


            <p>
                <strong>
                    Technical Accuracy:
                </strong>

                ${technicalAccuracy}/10
            </p>


            <p>
                <strong>
                    Relevance:
                </strong>

                ${relevance}/10
            </p>


            <p>
                <strong>
                    Clarity:
                </strong>

                ${clarity}/10
            </p>


            <p>
                <strong>
                    Completeness:
                </strong>

                ${completeness}/10
            </p>


            <p>
                <strong>
                    Performance:
                </strong>

                ${performance}
            </p>


            <h3>
                Observed Weaknesses
            </h3>

            ${listHtml(
                allWeaknesses
            )}


            <h3>
                Your Progress
            </h3>

            ${trendHtml}


            <button
                type="button"
                onclick="location.reload()"
            >
                Start New Interview
            </button>

        </div>
    `;
}


/* ============================================================
   AVERAGE
   ============================================================ */

function average(values) {

    if (!values.length) {
        return "0.0";
    }


    const numericValues =
        values
            .map(
                value =>
                    Number(value)
            )
            .filter(
                value =>
                    Number.isFinite(value)
            );


    if (!numericValues.length) {
        return "0.0";
    }


    return (
        numericValues.reduce(
            (sum, value) =>
                sum + value,
            0
        ) /
        numericValues.length
    ).toFixed(1);
}
