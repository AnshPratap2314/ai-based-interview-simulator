# AI Interview Preparation OS

AI Interview Preparation OS is a FastAPI + Gemini-powered interview simulator for practicing role-specific technical, HR, and AI/ML interviews.

## Features

- Role, difficulty, interview-type, and question-count selection
- Optional job-description-aware evaluation
- Gemini structured-output evaluation
- Technical accuracy, relevance, clarity, completeness, score, confidence, evidence, strengths, weaknesses, and improved answers
- Human-review safety flags for ambiguous, short, garbled, language-mismatched, off-topic, low-confidence, or inconsistent evaluations
- Candidate history and session history
- Separate candidate and interview-session credentials
- SQLite persistence for prototype/demo deployments
- Rate limiting and CORS controls
- Responsive frontend

## Project structure

```text
AI-Interview-Simulator/
├── Backend/
│   ├── main.py
│   ├── models.py
│   ├── evaluator.py
│   ├── storage.py
│   ├── security.py
│   ├── requirements.txt
│   ├── .env.example
│   └── tests/
├── Frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── docs/
├── README.md
└── LICENSE
```

## Local setup

### 1. Create a virtual environment

```bash
cd Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Gemini

Copy `.env.example` to `.env` and set your own Gemini API key.

Never commit `.env` or `history.db`.

### 3. Start the backend

```bash
cd Backend
uvicorn main:app --reload --port 8000
```

Open:

```text
http://127.0.0.1:8000/app/
```

## Separate frontend deployment

If the frontend is hosted separately, set `window.APP_API_URL` before `script.js` loads, for example:

```html
<script>
    window.APP_API_URL = "https://your-backend.example.com";
</script>
<script src="script.js"></script>
```

Also set `CORS_ORIGINS` on the backend to the exact frontend origin(s).

## Authentication design

The application uses two different credentials:

- **Candidate access token:** long-lived credential used for candidate history and for starting additional sessions for the same candidate.
- **Session token:** short-lived credential tied to one interview session and used for evaluation/session history.

Only token hashes are stored in SQLite.

## Testing

Static checks:

```bash
python3 -m py_compile Backend/*.py Backend/tests/*.py
node --check Frontend/script.js
```

Install development/test dependencies and run the deterministic regression suite:

```bash
pip install -r Backend/requirements-dev.txt
pytest Backend/tests/test_core.py -q
```

For the live Gemini regression suite, start the backend first and run:

```bash
python Backend/tests/run_eval.py --url http://127.0.0.1:8000
```

It creates a fresh candidate/session, imports the committed `eval_cases.py` definitions, and checks their expected HTTP status, score bounds, and human-review flags. It automatically honors `Retry-After` if a deployment rate-limits a case.

## Security notes

- Rotate any Gemini API key that was ever placed in an uploaded archive, repository, screenshot, or public deployment.
- Do not ship a local `.env`, SQLite database, Python virtual environment, IDE metadata, or OS metadata.
- The in-memory rate limiter is suitable for a single-process prototype. Multi-instance deployments should use a shared gateway/Redis limiter.
- SQLite is suitable for a hackathon/demo deployment; use managed PostgreSQL or another shared database for production scaling.
- `/health` is a liveness check; `/ready` performs both a database probe and Gemini configuration check and returns HTTP 503 when either is unavailable.
- Evaluation requests support an `X-Evaluation-Id` idempotency key scoped to the interview session and candidate, preventing duplicate history records after network retries.
- Rate-limit responses include `Retry-After` so clients and the live regression runner can retry safely.
- Never place a real API key in the ZIP, Git repository, frontend, screenshots, or browser code.

## Author

**Ansh Pratap**

Final Year B.Tech (Computer Science & Engineering)

## License

MIT License
