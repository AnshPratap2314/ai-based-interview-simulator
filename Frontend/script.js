const API_URL = (window.APP_API_URL || (window.location.protocol === "file:" ? "http://127.0.0.1:8000" : window.location.origin)).replace(/\/$/, "");
let sessionAccessToken = sessionStorage.getItem("interviewAccessToken") || "";

const questionBanks = {
    technical: {
        easy: ["What is OOP?", "What is DBMS?", "What is JavaScript?", "Explain HTML.", "What is CSS?", "What is a variable?", "What is a function?", "What is an array?", "What is a database?", "What is an API?"],
        medium: ["Explain the four pillars of OOP.", "What is normalization in DBMS?", "What is the difference between let, const and var?", "What is the difference between HTML and HTML5?", "Explain CSS Flexbox and Grid.", "What is a primary key and foreign key?", "What is exception handling?", "What is inheritance?", "What is REST API?", "Explain the difference between GET and POST."],
        hard: ["Explain polymorphism with a practical example.", "Explain database indexing and its advantages.", "Explain JavaScript closures.", "Explain event delegation in JavaScript.", "Explain ACID properties in DBMS.", "What are database transactions and isolation levels?", "Explain process vs thread.", "Explain time and space complexity.", "Explain RESTful API architecture.", "Explain authentication vs authorization."]
    },
    hr: {
        easy: ["Tell me about yourself.", "What are your strengths?", "What are your weaknesses?", "Why should we hire you?", "Where do you see yourself in five years?", "Why do you want this job?", "Tell me about your education.", "What motivates you?", "How do you handle pressure?", "What are your career goals?"],
        medium: ["Tell me about a challenging project you worked on.", "Describe a time you solved a difficult problem.", "How do you handle failure?", "Describe a situation where you worked in a team.", "How do you manage deadlines?", "Tell me about a conflict you handled.", "How do you prioritize multiple tasks?", "Describe a time you took initiative.", "What makes you different from other candidates?", "How do you handle criticism?"],
        hard: ["Tell me about your biggest professional failure and what you learned.", "Describe a situation where you disagreed with your manager.", "How would you handle an unethical request from a senior?", "Tell me about a time you made a decision with incomplete information.", "How would you handle failure on an important project?", "Describe a situation where you had to convince others.", "How would you respond if you received negative feedback unfairly?", "Tell me about a time you demonstrated leadership.", "What would you do if your team member was not contributing?", "Why should we choose you over a more experienced candidate?"]
    },
    aiml: {
        easy: ["What is Artificial Intelligence?", "What is Machine Learning?", "What is supervised learning?", "What is unsupervised learning?", "What is a dataset?", "What is a feature?", "What is a machine learning model?", "What is classification?", "What is regression?", "What is overfitting?"],
        medium: ["Explain the difference between supervised and unsupervised learning.", "Explain bias and variance.", "What is cross-validation?", "Explain precision, recall and F1-score.", "What is feature engineering?", "Explain gradient descent.", "What is the difference between classification and regression?", "Explain decision trees.", "What is a neural network?", "What is regularization?"],
        hard: ["Explain the bias-variance tradeoff in detail.", "Explain how backpropagation works.", "Compare CNNs, RNNs and Transformers.", "Explain gradient descent and its variants.", "How would you handle severe class imbalance?", "Explain precision-recall tradeoff and when it matters.", "How would you detect and prevent data leakage?", "Explain overfitting and different techniques to prevent it.", "How would you design an end-to-end ML system?", "Explain model deployment and monitoring in production."]
    }
};

let questions = [];
let currentQuestion = 0;
let totalQuestions = 5;
let interviewScores = [];
// session_id identifies ONE sitting. candidate_id identifies the PERSON across
// every sitting they ever do - that's what makes /history/candidate work.
let sessionId = crypto.randomUUID ? crypto.randomUUID() : `session-${Date.now()}`;
let candidateId = "";
let interviewContext = {};

/* ============================================================
   UI-only wiring: option cards / segmented buttons / avatar /
   char counter / progress indicator. None of this touches the
   evaluation logic below - it only keeps the hidden native
   <select> elements in sync so the existing functions keep
   reading the same values they always did.
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
        const initials = parts.length >= 2
            ? (parts[0][0] + parts[1][0])
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
    // Handles both .option-card (Interview Type / Difficulty) and
    // .segment (Number of Questions) - both use the same data-target/data-value pattern.
    document.querySelectorAll(".option-card, .segment").forEach((el) => {
        el.addEventListener("click", () => {
            const targetId = el.getAttribute("data-target");
            const value = el.getAttribute("data-value");
            const hiddenSelect = document.getElementById(targetId);
            if (!hiddenSelect) return;

            hiddenSelect.value = value;

            // Update visual state for this group only.
            const group = el.closest(".option-cards, .segmented");
            if (group) {
                group.querySelectorAll(".option-card, .segment").forEach((sibling) => {
                    sibling.classList.remove("active");
                    sibling.setAttribute("aria-pressed", "false");
                });
            }
            el.classList.add("active");
            el.setAttribute("aria-pressed", "true");

            updateProgress();
        });
    });
}

function syncOptionCardsFromSelects() {
    // Used after prefill, so the visible cards match whatever the
    // hidden selects currently hold (e.g. after localStorage restores a value).
    ["interviewType", "difficulty", "questionCount"].forEach((id) => {
        const select = document.getElementById(id);
        if (!select) return;
        document.querySelectorAll(`[data-target="${id}"]`).forEach((el) => {
            const isActive = el.getAttribute("data-value") === select.value;
            el.classList.toggle("active", isActive);
            el.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
    });
}

function updateProgress() {
    const indicator = document.getElementById("progressIndicator");
    if (!indicator) return;

    const nameFilled = document.getElementById("candidateId").value.trim().length > 0;
    const roleFilled = document.getElementById("role").value.trim().length > 0;
    // "Interview Setup" is always considered touched since every field has a default value.
    const setupDone = true;

    const steps = indicator.querySelectorAll(".progress-step");
    const states = [true, nameFilled, roleFilled, setupDone]; // step 1 (Candidate) is always reachable
    steps.forEach((step, i) => {
        step.classList.toggle("active", Boolean(states[i]));
    });
}

function initRoleField() {
    const roleField = document.getElementById("role");
    if (!roleField) return;
    roleField.addEventListener("input", updateProgress);
}

/* ============================================================
   Existing functionality below - unchanged behavior.
   ============================================================ */

function prefillSavedFields() {
    const rememberedRole = localStorage.getItem("lastRole");
    const roleField = document.getElementById("role");
    if (rememberedRole && roleField) {
        roleField.value = rememberedRole;
    }
}

// Call this once when the page loads.
document.addEventListener("DOMContentLoaded", () => {
    prefillSavedFields();
    initAvatar();
    initCharCount();
    initOptionCards();
    initRoleField();
    syncOptionCardsFromSelects();
    updateProgress();
});

async function startInterview() {
    const type = document.getElementById("interviewType").value;
    const difficulty = document.getElementById("difficulty").value;
    totalQuestions = parseInt(document.getElementById("questionCount").value, 10);

    const rawCandidateId = document.getElementById("candidateId").value.trim();
    candidateId = rawCandidateId || `guest-${Date.now()}`;

    const rawRole = document.getElementById("role").value.trim() || "Software Developer";
    localStorage.setItem("lastRole", rawRole);

    interviewContext = {
        role: rawRole,
        jobDescription: document.getElementById("jobDescription").value.trim(),
        type,
        difficulty
    };

    try {
        const sessionResponse = await fetch(`${API_URL}/session/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,
                candidate_id: candidateId,
                ...(sessionAccessToken ? { access_token: sessionAccessToken } : {})
            })
        });
        const sessionPayload = await sessionResponse.json().catch(() => ({}));
        if (!sessionResponse.ok) {
            throw new Error(sessionPayload.detail || "Unable to authorize the interview session.");
        }
        sessionAccessToken = sessionPayload.access_token;
        sessionStorage.setItem("interviewAccessToken", sessionAccessToken);
        candidateId = sessionPayload.candidate_id;
    } catch (error) {
        console.error(error);
        alert(error.message || "Unable to start the interview.");
        return;
    }

    questions = [...questionBanks[type][difficulty]].sort(() => Math.random() - 0.5).slice(0, totalQuestions);
    currentQuestion = 0;
    interviewScores = [];

    document.getElementById("setup").style.display = "none";
    document.getElementById("interview").style.display = "block";
    showQuestion();
}

function showQuestion() {
    document.getElementById("question").innerText = `Question ${currentQuestion + 1}/${totalQuestions}: ${questions[currentQuestion]}`;
    document.getElementById("answer").value = "";
    document.getElementById("result").innerHTML = "";
    // Empty string clears any inline override and lets the button CSS
    // (display: flex + margin: auto, which is what centers it) take over again.
    document.getElementById("submitButton").style.display = "";
    document.getElementById("submitButton").disabled = false;
    document.getElementById("nextButton").style.display = "none";
    document.getElementById("nextButton").innerText = currentQuestion === totalQuestions - 1 ? "Finish Interview" : "Next Question";
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;","\"":"&quot;"}[char]));
}

function listHtml(items) {
    return `<ul>${(items || []).map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

async function checkAnswer() {
    const answer = document.getElementById("answer").value.trim();
    const question = questions[currentQuestion];
    const result = document.getElementById("result");
    const submitButton = document.getElementById("submitButton");
    const nextButton = document.getElementById("nextButton");

    if (!answer) {
        result.innerText = "Please enter your answer first.";
        return;
    }

    result.innerText = "AI is evaluating your answer...";
    submitButton.disabled = true;

    try {
        const response = await fetch(`${API_URL}/evaluate`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Session-Token": sessionAccessToken
            },
            body: JSON.stringify({
                session_id: sessionId,
                candidate_id: candidateId,
                role: interviewContext.role,
                difficulty: interviewContext.difficulty,
                job_description: interviewContext.jobDescription,
                question,
                answer,
                expected_skills: []
            })
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload.detail || `Backend request failed: ${response.status}`);

        interviewScores.push(payload);

        result.innerHTML = `
            <h3>Overall Score: ${escapeHtml(payload.score)}/100</h3>
            <p><strong>Technical Accuracy:</strong> ${escapeHtml(payload.technical_accuracy)}/10</p>
            <p><strong>Relevance:</strong> ${escapeHtml(payload.relevance)}/10</p>
            <p><strong>Clarity:</strong> ${escapeHtml(payload.clarity)}/10</p>
            <p><strong>Completeness:</strong> ${escapeHtml(payload.completeness)}/10</p>
            <p><strong>Confidence:</strong> ${Math.round(Number(payload.confidence) * 100)}%</p>
            ${payload.needs_human_review ? '<p><strong>Review flag:</strong> This evaluation has low confidence or ambiguity. Review it before acting on the recommendation.</p>' : ''}
            <strong>Strengths:</strong>${listHtml(payload.strengths)}
            <strong>Weaknesses:</strong>${listHtml(payload.weaknesses)}
            <strong>Evidence:</strong>${listHtml(payload.evidence)}
            <p><strong>Feedback:</strong><br>${escapeHtml(payload.feedback)}</p>
            <p><strong>Improved Answer:</strong><br>${escapeHtml(payload.improved_answer)}</p>
        `;

        submitButton.style.display = "none";
        nextButton.style.display = "";
    } catch (error) {
        console.error(error);
        result.innerText = error.message || "Unable to connect to the AI backend. Please try again.";
        submitButton.disabled = false;
    }
}

function nextQuestion() {
    if (currentQuestion === totalQuestions - 1) {
        finishInterview();
        return;
    }
    currentQuestion++;
    showQuestion();
}

async function finishInterview() {
    if (!interviewScores.length) return;

    const averageScore = Math.round(interviewScores.reduce((sum, item) => sum + Number(item.score || 0), 0) / interviewScores.length);
    const technicalAccuracy = average(interviewScores.map(item => Number(item.technical_accuracy || 0)));
    const relevance = average(interviewScores.map(item => Number(item.relevance || 0)));
    const clarity = average(interviewScores.map(item => Number(item.clarity || 0)));
    const completeness = average(interviewScores.map(item => Number(item.completeness || 0)));
    const allWeaknesses = [...new Set(interviewScores.flatMap(item => item.weaknesses || []))];

    let performance = "Needs Improvement";
    if (averageScore >= 85) performance = "Excellent";
    else if (averageScore >= 70) performance = "Good";
    else if (averageScore >= 50) performance = "Average";

    let trendHtml = "<p>This is your first recorded session.</p>";
    try {
        const summaryResponse = await fetch(`${API_URL}/history/candidate/${encodeURIComponent(candidateId)}/summary`, { headers: { "X-Session-Token": sessionAccessToken } });
        if (summaryResponse.ok) {
            const summary = await summaryResponse.json();
            if (summary.sessions && summary.sessions.length > 1) {
                const rows = summary.sessions
                    .map((s, i) => `<li>Session ${i + 1}: avg ${s.average_score}/100 (${s.answered} answered) - ${escapeHtml(s.started_at)}</li>`)
                    .join("");
                trendHtml = `
                    <p>You've completed <strong>${summary.sessions.length} sessions</strong> under this profile.</p>
                    <ul>${rows}</ul>
                    <p><strong>Recurring weaknesses across sessions:</strong></p>
                    ${listHtml(summary.recurring_weaknesses)}
                `;
            }
        }
    } catch (error) {
        console.error("Could not load candidate trend:", error);
    }

    document.getElementById("interview").innerHTML = `
        <h1>Interview Report</h1>
        <div class="question-container">
            <p><strong>Role:</strong> ${escapeHtml(interviewContext.role)}</p>
            <p><strong>Overall Score:</strong> ${averageScore}/100</p>
            <p><strong>Questions Completed:</strong> ${interviewScores.length}/${totalQuestions}</p>
            <p><strong>Technical Accuracy:</strong> ${technicalAccuracy}/10</p>
            <p><strong>Relevance:</strong> ${relevance}/10</p>
            <p><strong>Clarity:</strong> ${clarity}/10</p>
            <p><strong>Completeness:</strong> ${completeness}/10</p>
            <p><strong>Performance:</strong> ${performance}</p>
            <h3>Observed Weaknesses (this session)</h3>
            ${listHtml(allWeaknesses)}
            <h3>Your Progress</h3>
            ${trendHtml}
            <button onclick="location.reload()">Start New Interview</button>
        </div>
    `;
}

function average(values) {
    if (!values.length) return 0;
    return (values.reduce((sum, value) => sum + Number(value || 0), 0) / values.length).toFixed(1);
}