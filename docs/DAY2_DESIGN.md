# Day 2 — Design / v0

## Goal
Upgrade the existing AI Interview Simulator into the first vertical slice of an AI Interview Preparation OS.

## v0 flow
Role + difficulty + question + candidate answer -> FastAPI -> Gemini -> structured evaluation -> Pydantic validation -> frontend.

## Input contract
`session_id`, `role`, `difficulty`, `question`, `answer`, and optional `expected_skills`.

## Output contract
Overall score, four category scores, strengths, weaknesses, evidence, feedback, improved answer, skill assessments, confidence, and human-review flag.

## Reliability boundary
- Empty input is rejected before an AI call.
- AI output is schema-validated.
- One retry is allowed after provider/validation failure.
- Low confidence (< 0.60) automatically sets `needs_human_review=true`.
- Provider failures return a safe 502 message rather than exposing internals.
- Candidate answer is explicitly treated as untrusted data to reduce prompt-injection risk.

## Secrets
API keys are read from environment variables. `.env.example` is safe to commit; `.env` must remain local/secret.

## Logging
Each evaluation logs request/session identifiers, attempt number, result score/confidence, and latency without logging candidate answer text.

## Deliberate scope
Persistent skill history, cross-session weakness tracking, JD skill extraction, and personalized practice planning are subsequent implementation slices. v0 first proves the reliable evaluation core end-to-end.
