"""
Run the full eval suite against a running backend and print pass/fail results.

Usage (from Backend/tests/):
    python run_eval.py
    python run_eval.py --url http://127.0.0.1:8000
    python run_eval.py --save results.json

Requires the backend to be running first (uvicorn main:app --reload --port 8000).
Requires the `requests` package: pip install requests --break-system-packages
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

from eval_cases import CASES


def run_case(base_url: str, case: dict) -> dict:
    payload = {
        "session_id": "eval-suite",
        "role": case.get("role", "Technical Interview"),
        "difficulty": case.get("difficulty", "medium"),
        "job_description": case.get("job_description", ""),
        "question": case["question"],
        "answer": case["answer"],
        "expected_skills": [],
    }

    started = time.perf_counter()
    try:
        response = requests.post(f"{base_url}/evaluate", json=payload, timeout=30)
    except requests.RequestException as exc:
        return {
            "name": case["name"],
            "passed": False,
            "reasons": [f"request failed: {exc}"],
            "latency_ms": None,
        }
    latency_ms = round((time.perf_counter() - started) * 1000)

    reasons = []

    if "expect_error" in case:
        passed = response.status_code == case["expect_error"]
        if not passed:
            reasons.append(
                f"expected HTTP {case['expect_error']}, got {response.status_code}"
            )
        return {
            "name": case["name"],
            "passed": passed,
            "reasons": reasons,
            "latency_ms": latency_ms,
        }

    if response.status_code != 200:
        return {
            "name": case["name"],
            "passed": False,
            "reasons": [f"unexpected HTTP {response.status_code}: {response.text[:200]}"],
            "latency_ms": latency_ms,
        }

    data = response.json()

    if "expect_min_score" in case and data.get("score", -1) < case["expect_min_score"]:
        reasons.append(f"score {data.get('score')} below minimum {case['expect_min_score']}")

    if "expect_max_score" in case and data.get("score", 999) > case["expect_max_score"]:
        reasons.append(f"score {data.get('score')} above maximum {case['expect_max_score']}")

    if "expect_human_review" in case and data.get("needs_human_review") != case["expect_human_review"]:
        reasons.append(
            f"needs_human_review was {data.get('needs_human_review')}, "
            f"expected {case['expect_human_review']}"
        )

    return {
        "name": case["name"],
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "latency_ms": latency_ms,
        "score": data.get("score"),
        "confidence": data.get("confidence"),
        "needs_human_review": data.get("needs_human_review"),
    }


def main():
    parser = argparse.ArgumentParser(description="Run the interview-evaluator test suite.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--save", default=None, help="Optional path to save results as JSON")
    args = parser.parse_args()

    print(f"Running {len(CASES)} test cases against {args.url}\n")

    results = []
    for case in CASES:
        result = run_case(args.url, case)
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        latency = f"{result['latency_ms']}ms" if result["latency_ms"] is not None else "n/a"
        extra = ""
        if "score" in result:
            extra = f" (score={result['score']}, confidence={result.get('confidence')}, review={result.get('needs_human_review')})"
        print(f"[{status}] {result['name']} - {latency}{extra}")

        for reason in result["reasons"]:
            print(f"       -> {reason}")

    passed = sum(r["passed"] for r in results)
    failed = len(results) - passed
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] is not None]
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else None

    print("\n" + "=" * 50)
    print(f"{passed}/{len(results)} passed, {failed} failed")
    if avg_latency is not None:
        print(f"Average latency: {avg_latency}ms")
    print("=" * 50)

    if args.save:
        out_path = Path(args.save)
        out_path.write_text(json.dumps(results, indent=2))
        print(f"\nSaved detailed results to {out_path}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()