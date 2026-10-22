#!/usr/bin/env python3
"""Publish LiveKit agent worker occupancy as CloudWatch Embedded Metric Format.

Runs as a sidecar next to the agent task. It polls the worker's local HTTP
``/worker`` endpoint and writes one EMF line per interval. The ECS ``awslogs``
driver ships that line to CloudWatch Logs, which extracts ``ActiveCalls`` and
``WorkerLoadPercent`` under ``AIReceptionist/Agent``.

``ActiveCalls`` is published once per task. Use the CloudWatch ``Average``
statistic to get calls per task, which is the correct utilisation signal for
ECS target tracking. Using ``Sum`` for target tracking would be unstable
because total calls do not fall when capacity is added.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_NAMESPACE = "AIReceptionist/Agent"
DEFAULT_SERVICE = "ai-receptionist-agent"
DEFAULT_ENVIRONMENT = "prod"
DEFAULT_URL = "http://127.0.0.1:8081/worker"


def build_metric_payload(
    *,
    active_jobs: int,
    worker_load: float,
    namespace: str,
    service: str,
    environment: str,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    """Return a CloudWatch EMF document for one worker sample."""
    if active_jobs < 0:
        raise ValueError("active_jobs must be >= 0")
    if not 0 <= worker_load <= 1:
        raise ValueError("worker_load must be between 0 and 1")
    if not namespace or not service or not environment:
        raise ValueError("namespace, service, and environment must be non-empty")

    return {
        "_aws": {
            "Timestamp": timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": namespace,
                    "Dimensions": [["Service", "Environment"]],
                    "Metrics": [
                        {"Name": "ActiveCalls", "Unit": "Count", "StorageResolution": 60},
                        {"Name": "WorkerLoadPercent", "Unit": "Percent", "StorageResolution": 60},
                    ],
                }
            ],
        },
        "Service": service,
        "Environment": environment,
        "ActiveCalls": int(active_jobs),
        "WorkerLoadPercent": round(float(worker_load) * 100, 2),
    }


def read_worker_info(url: str, timeout: float) -> tuple[int, float]:
    """Fetch and validate the LiveKit worker info payload."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read().decode("utf-8"))

    active_jobs = payload.get("active_jobs")
    worker_load = payload.get("worker_load", 0.0)
    if not isinstance(active_jobs, int) or active_jobs < 0:
        raise ValueError(f"invalid active_jobs in worker response: {active_jobs!r}")
    if not isinstance(worker_load, (int, float)) or not 0 <= float(worker_load) <= 1:
        raise ValueError(f"invalid worker_load in worker response: {worker_load!r}")
    return active_jobs, float(worker_load)


def emit_once(
    *,
    url: str,
    timeout: float,
    namespace: str,
    service: str,
    environment: str,
    stream: Any = sys.stdout,
) -> dict[str, Any]:
    active_jobs, worker_load = read_worker_info(url, timeout)
    payload = build_metric_payload(
        active_jobs=active_jobs,
        worker_load=worker_load,
        namespace=namespace,
        service=service,
        environment=environment,
    )
    stream.write(json.dumps(payload, separators=(",", ":")) + "\n")
    stream.flush()
    return payload


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=_env("AGENT_WORKER_URL", DEFAULT_URL))
    parser.add_argument(
        "--interval",
        type=_positive_float,
        default=float(_env("METRICS_INTERVAL_SECONDS", "15")),
    )
    parser.add_argument("--timeout", type=_positive_float, default=2.0)
    parser.add_argument("--namespace", default=_env("METRICS_NAMESPACE", DEFAULT_NAMESPACE))
    parser.add_argument("--service", default=_env("METRICS_SERVICE", DEFAULT_SERVICE))
    parser.add_argument("--environment", default=_env("METRICS_ENVIRONMENT", DEFAULT_ENVIRONMENT))
    parser.add_argument("--once", action="store_true", help="emit one sample and exit")
    args = parser.parse_args(argv)

    while True:
        try:
            emit_once(
                url=args.url,
                timeout=args.timeout,
                namespace=args.namespace,
                service=args.service,
                environment=args.environment,
            )
        except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
            print(f"metrics exporter: {exc}", file=sys.stderr, flush=True)

        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
