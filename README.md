# AI Interview Preparation OS — Final Superior Project

A unified AI interview simulator built from the strongest verified parts of three source projects. The final codebase uses the hardened backend/authentication/testing architecture from the strongest source implementation and the richer interview/question-history frontend behavior from the feature-rich implementation, while removing secrets, generated environments, local databases, IDE metadata, and duplicated project variants.

## Architecture

```text
Browser
  ↓
Responsive Frontend
  ↓
API Client
  ↓
FastAPI
  ├── Candidate access authentication
  ├── Interview session authentication + expiry
  ├── Validation
  ├── Rate limiting
  ├── Idempotent evaluation requests
  ├── Gemini evaluation + deterministic safety checks
  └── History / candidate summaries
          ↓
       SQLite (prototype)
```

## Features

- Role, difficulty, interview type and question-count selection
- Technical, HR and AI/ML question banks
- Question-history tracking to reduce immediate repeats
- Candidate-level persistent identity
- Separate candidate and interview-session credentials
- Session expiration and authorization
- Gemini structured evaluation
- Technical accuracy, relevance, clarity and completeness scoring
- Strengths, weaknesses, evidence, feedback and improved answers
- Confidence and human-review flags
- Evaluation idempotency via `X-Evaluation-Id`
- Session and candidate history
- Candidate performance summary and recurring weaknesses
- Pagination
- Rate limiting and `Retry-After`
- Readiness and health endpoints
- Responsive UI
- Safe HTML rendering for model-generated feedback
- Environment-based configuration

## Requirements

- Python 3.10+
- A Gemini API key for live AI evaluation

## Setup

```bash
cd Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Set `GEMINI_API_KEY` in `Backend/.env`.

Start the backend:

```bash
uvicorn main:app --reload --port 8000
```

Open `Frontend/index.html` for local development, or serve the frontend with a static HTTP server. When served separately, set `window.APP_API_URL` to the backend origin before loading `script.js`.

## Tests

Run from `Backend/`:

```bash
pytest -q tests/test_core.py
```

The deterministic suite uses a fake Gemini client, so it does not require a real API key.

## API

- `GET /` — service information
- `GET /health` — liveness
- `GET /ready` — readiness (database + Gemini configuration)
- `POST /session/start` — create an interview session
- `POST /evaluate` — evaluate an answer
- `GET /history/{session_id}` — session history
- `GET /history/candidate/{candidate_id}` — candidate history
- `GET /history/candidate/{candidate_id}/summary` — candidate summary
- `GET /app/` — bundled frontend when running the FastAPI server

## Security

Never commit `Backend/.env`, API keys, database files, virtual environments, IDE metadata, or generated caches. Use `.env.example` as the configuration template. Rotate any credential that was ever included in an exported project archive.

## Production notes

SQLite is retained as the prototype storage layer inherited from the source projects. For horizontally scaled production deployment, migrate to PostgreSQL and move rate limiting to a shared store such as Redis. Add HTTPS, centralized logging/monitoring, dependency scanning and browser E2E testing before a production launch.
