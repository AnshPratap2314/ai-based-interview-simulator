# AI Interview Preparation OS

> A full-stack AI-powered interview preparation platform that combines secure interview session management, Gemini-powered answer evaluation, persistent candidate history, intelligent question selection, performance analytics, and a responsive interview experience.

---

## 🚀 Overview

**AI Interview Preparation OS** is an AI-powered interview simulation and preparation platform designed to help students, job seekers, and developers practice realistic interviews and receive structured feedback on their answers.

The project combines:

- Secure candidate authentication
- Interview session management
- Technical, HR, and AI/ML interview question banks
- Intelligent question selection
- Question-history tracking
- Gemini-powered answer evaluation
- Deterministic answer-quality checks
- Structured interview feedback
- Candidate performance history
- Performance summaries
- Recurring weakness detection
- Rate limiting
- Evaluation idempotency
- Responsive frontend UI
- Automated backend regression testing

The current implementation uses **FastAPI, Python, SQLite, vanilla HTML/CSS/JavaScript, and Google Gemini**.

---

# ✨ Highlights

- 🤖 AI-powered interview evaluation
- 🎯 Technical, HR, and AI/ML interview modes
- 🧠 Intelligent question selection
- 🔄 Question-history tracking to reduce repeated questions
- 👤 Persistent candidate identity
- 🔐 Separate candidate and interview-session credentials
- ⏱️ Session expiration
- 🛡️ Authorization and validation
- 🚦 API rate limiting
- ♻️ Idempotent evaluation requests
- 📊 Candidate performance history
- 📈 Candidate performance summary
- 🧩 Recurring weakness detection
- 📝 Structured feedback and improved answers
- 🎯 Technical accuracy, relevance, clarity, and completeness evaluation
- 🔎 Evidence-based evaluation output
- ⚠️ Confidence and human-review indicators
- 📄 Paginated history
- ❤️ Health and readiness endpoints
- 📱 Responsive frontend
- 🧪 Automated backend regression tests
- 🔧 Environment-based configuration
- 🧹 Clean GitHub-ready project structure

---

# 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         USER / CANDIDATE                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    RESPONSIVE FRONTEND                      │
│                                                             │
│  HTML + CSS + JavaScript                                    │
│                                                             │
│  • Interview configuration                                  │
│  • Question presentation                                    │
│  • Answer submission                                        │
│  • Progress tracking                                        │
│  • Evaluation results                                       │
│  • History                                                  │
│  • Candidate summary                                        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                        FASTAPI API                          │
│                                                             │
│  • Authentication                                           │
│  • Session management                                       │
│  • Validation                                               │
│  • Rate limiting                                            │
│  • Evaluation idempotency                                   │
│  • History management                                       │
│  • Candidate summaries                                      │
└───────────────┬───────────────────────────────┬─────────────┘
                │                               │
                ▼                               ▼
┌─────────────────────────────┐     ┌─────────────────────────┐
│       EVALUATION ENGINE     │     │       STORAGE LAYER     │
│                             │     │                         │
│  Google Gemini              │     │  SQLite                 │
│  + deterministic checks     │     │                         │
│  + structured evaluation    │     │  • Sessions             │
│  + safety/review flags      │     │  • Evaluations          │
└─────────────────────────────┘     │  • Candidate history    │
                                    │  • Summaries             │
                                    └─────────────────────────┘
