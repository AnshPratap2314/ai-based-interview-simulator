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

let questions = [];
let currentQuestion = 0;
let totalQuestions = 5;
let interviewScores = [];
let interviewStarted = false;

function startInterview() {
    const type = document.getElementById("interviewType").value;
    const difficulty = document.getElementById("difficulty").value;
    totalQuestions = parseInt(document.getElementById("questionCount").value);

    questions = [...questionBanks[type][difficulty]]
        .sort(() => Math.random() - 0.5)
        .slice(0, totalQuestions);

    currentQuestion = 0;
    interviewScores = [];
    interviewStarted = true;

    document.getElementById("setup").style.display = "none";
    document.getElementById("interview").style.display = "block";

    showQuestion();
}

function showQuestion() {
    document.getElementById("question").innerText =
        `Question ${currentQuestion + 1}/${totalQuestions}: ${questions[currentQuestion]}`;

    document.getElementById("answer").value = "";
    document.getElementById("result").innerText = "";

    document.getElementById("submitButton").style.display = "inline-block";
    document.getElementById("nextButton").style.display = "none";

    if (currentQuestion === totalQuestions - 1) {
        document.getElementById("nextButton").innerText = "Finish Interview";
    } else {
        document.getElementById("nextButton").innerText = "Next Question";
    }
}

async function checkAnswer() {
    const answer = document.getElementById("answer").value.trim();
    const question = questions[currentQuestion];
    const result = document.getElementById("result");

    if (!answer) {
        result.innerText = "Please enter your answer first.";
        return;
    }

    result.innerText = "AI is evaluating your answer...";

    document.getElementById("submitButton").disabled = true;

    try {
        const response = await fetch("http://127.0.0.1:8000/evaluate", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                question: question,
                answer: answer
            })
        });

        if (!response.ok) {
            throw new Error("Backend request failed");
        }

        const data = await response.json();

        interviewScores.push(data);

        result.innerHTML =
            `<strong>Overall Score: ${data.score}/100</strong><br><br>` +
            `Technical Accuracy: ${data.technical_accuracy}/10<br>` +
            `Relevance: ${data.relevance}/10<br>` +
            `Clarity: ${data.clarity}/10<br>` +
            `Completeness: ${data.completeness}/10<br><br>` +
            `<strong>Strengths:</strong><br>${data.strengths}<br><br>` +
            `<strong>Weaknesses:</strong><br>${data.weaknesses}<br><br>` +
            `<strong>Feedback:</strong><br>${data.feedback}<br><br>` +
            `<strong>Improved Answer:</strong><br>${data.improved_answer}`;

        document.getElementById("submitButton").style.display = "none";
        document.getElementById("submitButton").disabled = false;
        document.getElementById("nextButton").style.display = "inline-block";

    } catch (error) {
        console.error(error);

        result.innerText =
            "Unable to connect to the AI backend. Make sure FastAPI is running.";

        document.getElementById("submitButton").disabled = false;
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

function finishInterview() {
    if (interviewScores.length === 0) {
        return;
    }

    const totalScore = interviewScores.reduce(
        (sum, item) => sum + item.score,
        0
    );

    const averageScore = Math.round(
        totalScore / interviewScores.length
    );

    const technicalAccuracy = average(
        interviewScores.map(item => item.technical_accuracy)
    );

    const relevance = average(
        interviewScores.map(item => item.relevance)
    );

    const clarity = average(
        interviewScores.map(item => item.clarity)
    );

    const completeness = average(
        interviewScores.map(item => item.completeness)
    );

    let performance = "Needs Improvement";

    if (averageScore >= 85) {
        performance = "Excellent";
    } else if (averageScore >= 70) {
        performance = "Good";
    } else if (averageScore >= 50) {
        performance = "Average";
    }

    document.getElementById("interview").innerHTML = `
        <h1>AI Interview Simulator</h1>

        <h2>FINAL INTERVIEW REPORT</h2>

        <p><strong>Interview Completed!</strong></p>

        <p><strong>Overall Score:</strong> ${averageScore}/100</p>

        <p><strong>Questions Completed:</strong> ${interviewScores.length}/${totalQuestions}</p>

        <p><strong>Technical Accuracy:</strong> ${technicalAccuracy}/10</p>

        <p><strong>Relevance:</strong> ${relevance}/10</p>

        <p><strong>Clarity:</strong> ${clarity}/10</p>

        <p><strong>Completeness:</strong> ${completeness}/10</p>

        <p><strong>Performance:</strong> ${performance}</p>

        <p>Keep practicing and focus on giving detailed explanations with practical examples.</p>

        <br>

        <button onclick="location.reload()">Start New Interview</button>
    `;
}

function average(values) {
    const total = values.reduce((sum, value) => sum + value, 0);

    return (total / values.length).toFixed(1);
}