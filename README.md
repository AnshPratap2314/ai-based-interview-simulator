# 🤖 AI Interview Simulator

An AI-powered interview preparation platform that simulates technical interviews, evaluates candidate answers using Google Gemini, provides structured feedback, identifies recurring weaknesses, and maintains persistent interview history.

The project is designed to help students, job seekers, and software-engineering candidates practice realistic interviews and understand exactly where they can improve.

---

## 🚀 Live Demo

**Frontend / Application:**
https://ai-based-interview-simulator-1.onrender.com

**GitHub Repository:**
https://github.com/AnshPratap2314/ai-based-interview-simulator

---

## ✨ Overview

The **AI Interview Simulator** provides an end-to-end interview practice experience:

```text
Candidate
   ↓
Interview Setup
   ↓
Session Creation
   ↓
Interview Question
   ↓
Candidate Answer
   ↓
FastAPI Backend
   ↓
Google Gemini AI
   ↓
Structured Evaluation
   ↓
Score + Feedback + Evidence
   ↓
SQLite Persistence
   ↓
Interview History
   ↓
Candidate Performance Summary
```

Instead of simply generating an overall score, the system evaluates multiple dimensions of an answer and provides actionable feedback.

---

# 🎯 Key Features

## 🧑‍💻 AI-Powered Interview Evaluation

Candidate answers are evaluated using Google Gemini.

The evaluation includes:

* Overall score
* Technical accuracy
* Relevance
* Clarity
* Completeness
* Confidence
* Strengths
* Weaknesses
* Evidence from the candidate's answer
* Improvement feedback
* Improved answer
* Skills assessed
* Human-review indicator

---

## 🎤 Interview Simulation

Candidates can simulate software-engineering interviews with:

* Candidate identification
* Role selection
* Difficulty selection
* Job description support
* Technical questions
* HR questions
* AI/ML-oriented questions
* Multiple-question interviews
* Progress tracking
* Final performance report

---

## 📊 Structured AI Evaluation

Each answer is evaluated using multiple dimensions:

| Dimension          | Purpose                                            |
| ------------------ | -------------------------------------------------- |
| Technical Accuracy | Checks correctness of technical concepts           |
| Relevance          | Measures whether the answer addresses the question |
| Clarity            | Evaluates how clearly the candidate communicates   |
| Completeness       | Checks whether important aspects were covered      |
| Confidence         | AI-generated confidence estimate                   |
| Overall Score      | Combined AI evaluation score                       |

Example evaluation:

```json
{
  "score": 75,
  "technical_accuracy": 10,
  "relevance": 10,
  "clarity": 9,
  "completeness": 6,
  "confidence": 0.95,
  "needs_human_review": false
}
```

---

# 🧠 AI Feedback System

The simulator does more than assign a score.

It identifies:

### Strengths

Examples:

* Correct technical concepts
* Clear explanation
* Appropriate terminology
* Direct response

### Weaknesses

Examples:

* Missing real-world examples
* Missing complexity analysis
* Incomplete explanation
* Missing implementation details

### Evidence

The system identifies evidence from the candidate's response that supports the evaluation.

### Improved Answer

The AI generates a stronger version of the candidate's answer that can be used for learning and interview preparation.

---

# 📈 Candidate Performance History

Interview evaluations are stored in SQLite.

Candidates can retrieve:

* Previous answers
* Scores
* Technical accuracy
* Relevance
* Clarity
* Completeness
* Confidence
* Weaknesses
* Session information
* Evaluation timestamps

The system also provides a candidate-level summary.

Example:

```json
{
  "candidate_id": "test-user-001",
  "total_answers": 1,
  "sessions": [
    {
      "session_id": "test-session-001",
      "answered": 1,
      "average_score": 75.0
    }
  ],
  "recurring_weaknesses": [
    "Missing real-world use cases",
    "Missing complexity analysis"
  ]
}
```

---

# 🔐 Security

The backend includes authentication and authorization mechanisms.

## Session Tokens

Each interview session receives an access token.

The token is passed using:

```http
X-Session-Token: <token>
```

## Candidate Authorization

Candidates can only access their own interview history.

Cross-candidate access is rejected.

Example:

```text
Candidate A → Candidate A data     ✅
Candidate A → Candidate B data     ❌ 403
```

## Request Validation

Invalid requests are rejected using FastAPI/Pydantic validation.

Examples:

```text
Missing required fields → 422
Empty answer            → 422
Missing question        → 422
Invalid authorization   → 403
```

## Rate Limiting

The API implements rate limiting to protect the evaluation endpoint from excessive requests.

During testing:

```text
Requests 1–10  → 200
Requests 11+  → 429
```

---

# 🏗️ System Architecture

```text
┌─────────────────────────────┐
│        Frontend             │
│     HTML / CSS / JS         │
└──────────────┬──────────────┘
               │ HTTP/JSON
               ▼
┌─────────────────────────────┐
│        FastAPI Backend      │
│                             │
│ • Authentication            │
│ • Authorization             │
│ • Validation                │
│ • Rate Limiting             │
│ • Session Management        │
│ • Evaluation API            │
└──────────────┬──────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌──────────────┐  ┌────────────────┐
│ Google Gemini│  │ SQLite Database │
│     AI       │  │                │
└──────────────┘  └────────────────┘
```

---

# 🛠️ Technology Stack

## Frontend

* HTML5
* CSS3
* JavaScript
* Responsive UI
* Browser Local Storage
* Browser Session Storage
* Fetch API

## Backend

* Python
* FastAPI
* Uvicorn
* Pydantic
* SQLite

## Artificial Intelligence

* Google Gemini API
* AI-based answer evaluation
* Structured feedback generation
* Skill assessment
* Confidence estimation

## Development Tools

* Git
* GitHub
* VS Code
* macOS
* cURL

---

# 📁 Project Structure

```text
AI-Interview-Simulator/
│
├── Backend/
│   ├── .env.example
│   ├── evaluator.py
│   ├── main.py
│   ├── models.py
│   ├── requirements.txt
│   ├── security.py
│   ├── storage.py
│   │
│   └── tests/
│       ├── eval_cases.py
│       └── run_eval.py
│
├── Frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
│
├── docs/
│   └── DAY2_DESIGN.md
│
├── .gitignore
├── LICENSE
└── README.md
```

---

# 🔌 API Endpoints

## Health Check

```http
GET /health
```

Used to verify that the backend is running.

---

## Root

```http
GET /
```

Returns the API/application root response.

---

## Start Interview Session

```http
POST /session/start
```

Example:

```json
{
  "candidate_id": "candidate-001",
  "session_id": "session-001"
}
```

Returns an authentication token.

---

## Evaluate Answer

```http
POST /evaluate
```

Requires:

```http
X-Session-Token: <token>
```

Example:

```json
{
  "session_id": "session-001",
  "candidate_id": "candidate-001",
  "role": "Software Engineer",
  "difficulty": "medium",
  "question": "What is the difference between a stack and a queue?",
  "answer": "A stack follows LIFO while a queue follows FIFO.",
  "expected_skills": [
    "Data Structures",
    "Algorithms"
  ]
}
```

---

## Candidate History

```http
GET /history/candidate/{candidate_id}
```

Requires:

```http
X-Session-Token: <token>
```

Returns the candidate's previous evaluations.

---

## Session History

```http
GET /history/{session_id}
```

Returns evaluations associated with an interview session.

---

## Candidate Summary

```http
GET /history/candidate/{candidate_id}/summary
```

Returns:

* Total answers
* Interview sessions
* Average scores
* Recurring weaknesses

---

# ⚙️ Local Setup

## 1. Clone the repository

```bash
git clone https://github.com/AnshPratap2314/ai-based-interview-simulator.git
```

```bash
cd ai-based-interview-simulator
```

---

## 2. Create a Python virtual environment

```bash
python3 -m venv venv
```

Activate it:

### macOS / Linux

```bash
source venv/bin/activate
```

### Windows

```bash
venv\Scripts\activate
```

---

## 3. Install backend dependencies

```bash
cd Backend
pip install -r requirements.txt
```

---

## 4. Configure Gemini API

Create:

```text
Backend/.env
```

Add:

```env
GEMINI_API_KEY=your_gemini_api_key
```

### ⚠️ Security

Never commit your real API key to GitHub.

The repository contains:

```text
.env.example
```

for configuration reference.

---

# ▶️ Run the Backend

From the `Backend` directory:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend:

```text
http://127.0.0.1:8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

---

# 🌐 Run the Frontend

Open another terminal:

```bash
cd Frontend
```

Start a local static server:

```bash
python3 -m http.server 5500
```

Open:

```text
http://127.0.0.1:5500
```

---

# 🧪 Testing

The project has been tested across the major backend workflows.

## Backend Tests

### Health

```text
GET /health
→ 200 OK
```

### Session Creation

```text
POST /session/start
→ 200 OK
```

### Gemini Evaluation

```text
POST /evaluate
→ 200 OK
```

### History

```text
GET /history/candidate/{candidate_id}
→ 200 OK
```

### Candidate Summary

```text
GET /history/candidate/{candidate_id}/summary
→ 200 OK
```

---

# 🔒 Security Testing

The following security scenarios were verified:

```text
No token
→ 403 Forbidden

Invalid token
→ 403 Forbidden

Cross-candidate history access
→ 403 Forbidden

Cross-candidate evaluation
→ 403 Forbidden
```

---

# 🧾 Input Validation Testing

The following invalid requests were tested:

```text
Empty request
→ 422 Unprocessable Entity

Empty answer
→ 422 Unprocessable Entity

Missing question
→ 422 Unprocessable Entity
```

---

# 🚦 Rate Limiting Test

The evaluation endpoint was tested with repeated requests.

Observed behavior:

```text
Request 1  → 200
Request 2  → 200
...
Request 10 → 200
Request 11 → 429
Request 12 → 429
...
```

This confirms that excessive requests are being throttled.

---

# 💾 Persistence Testing

The application was tested by:

1. Creating an interview session
2. Evaluating an answer
3. Saving the evaluation
4. Stopping the backend
5. Restarting the backend
6. Requesting the candidate history again

The evaluation remained available after restart.

Therefore:

```text
AI Evaluation
      ↓
SQLite
      ↓
Backend Restart
      ↓
History Still Available
```

---

# 📱 Responsive Design

The frontend is designed to work across:

* Desktop
* Laptop
* Tablet
* Mobile phones

The interface uses responsive CSS and adaptive layouts to provide a usable interview experience across different screen sizes.

---

# 🔄 Complete User Flow

```text
1. Open Application
        ↓
2. Enter Candidate Information
        ↓
3. Select Interview Role
        ↓
4. Select Difficulty
        ↓
5. Add Job Description
        ↓
6. Select Number of Questions
        ↓
7. Start Interview
        ↓
8. Receive Question
        ↓
9. Submit Answer
        ↓
10. AI Evaluates Answer
        ↓
11. View Score & Feedback
        ↓
12. Continue Interview
        ↓
13. Complete Questions
        ↓
14. View Final Report
        ↓
15. Review Performance History
```

---

# 🎯 Example Use Case

### Question

> What is the difference between a stack and a queue?

### Candidate Answer

> A stack follows LIFO while a queue follows FIFO. Stack operations include push and pop, while queue operations include enqueue and dequeue.

### AI Evaluation

```text
Overall Score: 75

Technical Accuracy: 10
Relevance:          10
Clarity:             9
Completeness:        6
Confidence:          0.95
```

### AI Feedback

The system identifies missing:

* Real-world use cases
* Complexity discussion
* Implementation details

and generates an improved answer for learning.

---

# 📌 Design Goals

The project focuses on:

* Practical interview preparation
* AI-assisted learning
* Structured evaluation
* Actionable feedback
* Candidate performance tracking
* Secure session-based access
* Persistent interview history
* Responsive user experience

---

# 🔮 Future Improvements

Potential future enhancements include:

* Voice-based interviews
* Speech-to-text answer processing
* Real-time interview mode
* Webcam-based interview simulation
* Facial-expression analysis
* Advanced resume/JD matching
* Personalized interview question generation
* Adaptive difficulty
* More detailed performance analytics
* Skill-wise progress tracking
* Leaderboards
* Interview analytics dashboard
* Redis-based distributed rate limiting
* Production-grade observability
* Automated CI/CD
* Docker deployment
* Kubernetes deployment
* Multi-model AI evaluation
* Human evaluator dashboard

---

# 🧩 Known Engineering Considerations

The current implementation uses an in-memory rate limiter. This works for a single backend instance, but a production multi-instance deployment should use a shared mechanism such as Redis or an API gateway.

The AI-generated overall score and individual dimension scores are generated by the evaluation model. A future version could use deterministic score aggregation if strict mathematical consistency between dimensions and overall score is required.

---

# 👨‍💻 Author

**Ansh Pratap**

B.Tech Computer Science & Engineering
Mewar University, Rajasthan

### Interests

* Artificial Intelligence
* Machine Learning
* Software Engineering
* Generative AI
* Backend Development
* Full-Stack Development

---

# 📜 License

This project is available under the license included in the repository.

See:

```text
LICENSE
```

---

# ⭐ Support

If you find this project useful, consider giving the repository a ⭐ on GitHub.

**Repository:**
https://github.com/AnshPratap2314/ai-based-interview-simulator

---

## 🚀 Project Status

**Status: Functional and tested**

Core functionality including:

```test
AI Evaluation       ✅
Authentication      ✅
Authorization       ✅
Input Validation    ✅
Rate Limiting       ✅
Database Storage    ✅
History             ✅
Candidate Summary   ✅
Persistence         ✅
Responsive UI       ✅
```

The project is actively suitable for further development toward a production-ready AI interview preparation platform.
