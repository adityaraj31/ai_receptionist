from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

import metrics_exporter


class EmfPayloadTest(unittest.TestCase):
    def test_payload_has_cloudwatch_contract(self) -> None:
        payload = metrics_exporter.build_metric_payload(
            active_jobs=3,
            worker_load=0.42,
            namespace="Test/Agents",
            service="agent",
            environment="test",
            timestamp_ms=1_700_000_000_000,
        )

        self.assertEqual(payload["ActiveCalls"], 3)
        self.assertEqual(payload["WorkerLoadPercent"], 42.0)
        self.assertEqual(payload["_aws"]["Timestamp"], 1_700_000_000_000)
        metric_directive = payload["_aws"]["CloudWatchMetrics"][0]
        self.assertEqual(metric_directive["Namespace"], "Test/Agents")
        self.assertEqual(metric_directive["Dimensions"], [["Service", "Environment"]])
        self.assertEqual(
            [metric["Name"] for metric in metric_directive["Metrics"]],
            ["ActiveCalls", "WorkerLoadPercent"],
        )

    def test_rejects_out_of_range_values(self) -> None:
        with self.assertRaises(ValueError):
            metrics_exporter.build_metric_payload(
                active_jobs=-1,
                worker_load=0.2,
                namespace="Test/Agents",
                service="agent",
                environment="test",
            )
        with self.assertRaises(ValueError):
            metrics_exporter.build_metric_payload(
                active_jobs=1,
                worker_load=1.2,
                namespace="Test/Agents",
                service="agent",
                environment="test",
            )

    @patch("metrics_exporter.read_worker_info", return_value=(4, 0.5))
    def test_emit_once_writes_single_json_line(self, _read_worker_info) -> None:
        stream = io.StringIO()
        payload = metrics_exporter.emit_once(
            url="http://agent/worker",
            timeout=1,
            namespace="Test/Agents",
            service="agent",
            environment="test",
            stream=stream,
        )

        lines = stream.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]), payload)


if __name__ == "__main__":
    unittest.main()
