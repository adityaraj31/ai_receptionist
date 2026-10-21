#!/usr/bin/env python3
"""Retrieval eval for the clinic FAQ knowledge base.

Run from the repository root against a running API:
    cd api && uv run python ../evals/run_faq_eval.py

The runner seeds nothing. Ingest the corpus first:
    uv run python -m scripts.ingest_faqs --clinic-id <uuid> --replace

It reports recall@1 and end-to-end p50/p95 latency (HTTP + embedding + pgvector). It
fails if recall drops below --min-recall or p95 exceeds --max-latency-ms.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "agent" / ".env")
load_dotenv(ROOT / "api" / ".env")

DATASET = ROOT / "evals" / "faq_eval.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("AGENT_API_URL")
        or os.getenv("API_BASE_URL")
        or "http://localhost:8000",
    )
    parser.add_argument(
        "--key",
        default=os.getenv("AGENT_API_KEY") or os.getenv("DEMO_AGENT_KEY"),
    )
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--max-latency-ms", type=float, default=300.0)
    parser.add_argument("--min-recall", type=float, default=0.8)
    parser.add_argument("--warmup", type=int, default=2)
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"{path} must contain a non-empty list of cases")
    return cases


def normalize(value: str | None) -> str:
    return " ".join((value or "").lower().split()).strip(" .?!")


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]


def search(client: httpx.Client, query: str) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    response = client.post("/api/v1/agent/faq/search", json={"query": query})
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    return response.json(), elapsed_ms


def main() -> None:
    args = parse_args()
    if not args.key:
        raise SystemExit("Set DEMO_AGENT_KEY or AGENT_API_KEY (or pass --key)")

    cases = load_cases(args.dataset)
    headers = {"X-Service-Key": args.key}

    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        headers=headers,
        timeout=20.0,
    ) as client:
        for _ in range(max(0, args.warmup)):
            search(client, "clinic timings")

        hits = 0
        latencies: list[float] = []
        failures: list[str] = []

        for case in cases:
            query = case["query"]
            expected = case["expected_question"]
            try:
                body, elapsed_ms = search(client, query)
            except httpx.HTTPError as exc:
                failures.append(f"ERROR {query!r}: {exc}")
                print(f"ERROR  {query!r}: {exc}")
                continue

            latencies.append(elapsed_ms)
            returned = body.get("question")
            matched = body.get("found") is True and normalize(returned) == normalize(expected)
            hits += int(matched)
            status = "PASS" if matched else "FAIL"
            if not matched:
                failures.append(
                    f"{status} {query!r}: expected {expected!r}, got {returned!r}"
                )
            print(
                f"{status}  {elapsed_ms:6.1f} ms  score={body.get('score', 0):.3f}  "
                f"{query} -> {returned}"
            )

        recall = hits / len(cases) if cases else 0.0
        p50 = statistics.median(latencies) if latencies else 0.0
        p95 = percentile(latencies, 0.95)

    print()
    print(f"cases: {len(cases)}  recall@1: {recall:.2f}  p50: {p50:.1f} ms  p95: {p95:.1f} ms")
    print(f"targets: recall >= {args.min_recall:.2f}, p95 <= {args.max_latency_ms:.0f} ms")
    print("latency includes HTTP, local embedding, and the pgvector round trip.")

    failed = bool(failures) or recall < args.min_recall or p95 > args.max_latency_ms
    if failures:
        print()
        for failure in failures:
            print(failure)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
