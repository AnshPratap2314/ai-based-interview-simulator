#!/usr/bin/env python3
import argparse
import sys
import time
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_cases import CASES


def _check_expected(case, result):
    score = result.get("score")
    if not isinstance(score, int) or not 0 <= score <= 100:
        return False, "invalid score"
    confidence = result.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        return False, "invalid confidence"
    minimum = case.get("expect_min_score")
    maximum = case.get("expect_max_score")
    if minimum is not None and score < minimum:
        return False, f"score {score} < minimum {minimum}"
    if maximum is not None and score > maximum:
        return False, f"score {score} > maximum {maximum}"
    expected_review = case.get("expect_human_review")
    if expected_review is not None and bool(result.get("needs_human_review")) != expected_review:
        return False, f"needs_human_review={result.get('needs_human_review')} expected {expected_review}"
    return True, ""


def main():
    parser = argparse.ArgumentParser(description="Run the committed Gemini evaluation regression cases.")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--candidate", default=f"eval-{uuid.uuid4().hex[:12]}")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    base = args.url.rstrip("/")

    try:
        health = requests.get(f"{base}/health", timeout=10)
        health.raise_for_status()
        ready = requests.get(f"{base}/ready", timeout=10)
        ready.raise_for_status()
        if ready.json().get("status") != "ready":
            print("FAIL: backend is not ready", ready.text)
            return 1
    except requests.RequestException as exc:
        print(f"FAIL: backend unavailable: {exc}")
        return 1

    session_id = str(uuid.uuid4())
    try:
        started = requests.post(
            f"{base}/session/start",
            json={"candidate_id": args.candidate, "session_id": session_id},
            timeout=10,
        )
        started.raise_for_status()
        session = started.json()
        session_token = session["session_token"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        print(f"FAIL: session creation: {exc}")
        return 1

    failures = 0
    for index, case in enumerate(CASES, start=1):
        payload = {
            "session_id": session_id,
            "candidate_id": args.candidate,
            "role": case["role"],
            "difficulty": case["difficulty"],
            "job_description": case.get("job_description", ""),
            "question": case["question"],
            "answer": case["answer"],
            "expected_skills": case.get("expected_skills", []),
        }
        evaluation_id = str(uuid.uuid4())
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{base}/evaluate",
                    json=payload,
                    headers={"X-Session-Token": session_token, "X-Evaluation-Id": evaluation_id},
                    timeout=args.timeout,
                )
            except requests.RequestException as exc:
                print(f"FAIL {case['name']}: {exc}")
                failures += 1
                break
            if response.status_code == 429 and attempt < 2:
                retry_after = int(response.headers.get("Retry-After", "1"))
                print(f"WAIT {case['name']}: rate limit; retrying in {retry_after}s")
                time.sleep(min(retry_after, 120))
                continue
            expected_error = case.get("expect_error")
            if expected_error is not None:
                ok = response.status_code == expected_error
                reason = "" if ok else f"HTTP {response.status_code}, expected {expected_error}"
            else:
                ok = response.status_code == 200
                reason = ""
                if ok:
                    try:
                        result = response.json()
                        ok, reason = _check_expected(case, result)
                    except ValueError as exc:
                        ok, reason = False, f"invalid JSON: {exc}"
                else:
                    reason = response.text[:500]
            print(f"{'PASS' if ok else 'FAIL'} {index:02d} {case['name']}: HTTP {response.status_code}{(' - ' + reason) if reason else ''}")
            if not ok:
                failures += 1
            break

    print(f"\nCompleted {len(CASES)} cases; failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
