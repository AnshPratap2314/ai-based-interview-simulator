# Merge Decisions

## Project A

Selected as the primary backend foundation because it provides the strongest verified authentication, session expiry, persistence, idempotency, pagination, rate limiting, evaluator safeguards and deterministic regression tests.

## Project B

Used as a reference for intermediate implementations only. Its packaged virtual environment, local database, IDE/OS metadata and older implementation patterns were intentionally excluded.

## Project C

Selected for the richer frontend interview experience, especially question-history and question-selection behavior, while its weaker candidate/session credential integration was rewritten to use Project A's two-token contract.

## Rewritten

- Frontend authentication/session handling was reconciled around `candidate_access_token` and `session_token`.
- Candidate summary/history requests use the candidate access token.
- Evaluation requests use the session token.
- Per-question `X-Evaluation-Id` values were added for backend idempotency.
- Runtime API URL selection was made environment/deployment friendly.
- Project packaging was rebuilt without secrets, local DB state, `.venv`, `.git`, `.idea`, `.DS_Store` and `__pycache__` artifacts.

## Removed

- Real `.env` files and credentials
- Bundled SQLite database state
- Bundled virtual environments
- IDE and OS metadata
- Git repositories from source ZIPs
- Duplicate backend implementations
