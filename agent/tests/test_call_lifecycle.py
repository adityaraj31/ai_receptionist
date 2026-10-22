from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx

from api_client import AgentApiClient
from call_lifecycle import CallLifecycle
from recording import RecordingSession


def run(coro: Any) -> Any:
    return asyncio.run(coro)


class FakeRecording:
    def __init__(self, metadata: dict[str, Any] | None = None) -> None:
        self.metadata = metadata
        self.stopped = False
        self.closed = False

    async def stop(self) -> dict[str, Any] | None:
        self.stopped = True
        return self.metadata

    async def close(self) -> None:
        self.closed = True


class FakeApi:
    def __init__(self, api_key: str = "test-key", fail_times: int = 0) -> None:
        self.api_key = api_key
        self.fail_times = fail_times
        self.payloads: list[dict[str, Any]] = []
        self.closed = False

    async def finalize_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.fail_times:
            self.fail_times -= 1
            raise RuntimeError("temporary failure")
        self.payloads.append(payload)
        return {"call_id": "call-123", "queued": True}

    async def aclose(self) -> None:
        self.closed = True


def make_lifecycle(
    *,
    api: FakeApi | None = None,
    recording: FakeRecording | None = None,
) -> tuple[CallLifecycle, list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []

    def on_event(event: str, **fields: Any) -> None:
        events.append({"event": event, **fields})

    lifecycle = CallLifecycle(
        api=api or FakeApi(),  # type: ignore[arg-type]
        room_name="call-room-1",
        started_at=datetime(2026, 10, 21, 9, 0, tzinfo=UTC),
        from_number="+919000000001",
        to_number="+919000000002",
        language="hi-IN",
        on_event=on_event,
        recording=recording or FakeRecording(),  # type: ignore[arg-type]
    )
    return lifecycle, events


def test_usage_collector_accumulates_provider_metrics() -> None:
    lifecycle, _ = make_lifecycle()
    lifecycle.usage.on_stt_metrics(SimpleNamespace(audio_duration=1.5))
    lifecycle.usage.on_stt_metrics(SimpleNamespace(audio_duration=2.0))
    lifecycle.usage.on_llm_metrics(SimpleNamespace(prompt_tokens=100, completion_tokens=20))
    lifecycle.usage.on_llm_metrics(SimpleNamespace(prompt_tokens=50, completion_tokens=10))
    lifecycle.usage.on_tts_metrics(SimpleNamespace(characters_count=300))

    assert lifecycle.usage.as_dict() == {
        "stt_audio_seconds": 3.5,
        "llm_prompt_tokens": 150,
        "llm_completion_tokens": 30,
        "tts_characters": 300,
        "average_latency_ms": None,
        "latency_samples": 0,
    }


def test_usage_collector_averages_turn_latency() -> None:
    lifecycle, _ = make_lifecycle()
    lifecycle.on_conversation_item(
        SimpleNamespace(
            item=SimpleNamespace(
                role="assistant",
                text_content="One",
                metrics={"e2e_latency": 0.8},
            )
        )
    )
    lifecycle.on_conversation_item(
        SimpleNamespace(
            item=SimpleNamespace(
                role="assistant",
                text_content="Two",
                metrics={"e2e_latency": 1.2},
            )
        )
    )
    lifecycle.on_conversation_item(
        SimpleNamespace(item=SimpleNamespace(role="user", text_content="Hi", metrics={}))
    )

    assert lifecycle.usage.as_dict() == {
        "stt_audio_seconds": 0.0,
        "llm_prompt_tokens": 0,
        "llm_completion_tokens": 0,
        "tts_characters": 0,
        "average_latency_ms": 1000.0,
        "latency_samples": 2,
    }


def test_lifecycle_submits_transcript_usage_and_recording() -> None:
    recording = FakeRecording(
        {
            "egress_id": "EG_1",
            "url": "s3://bucket/recordings/call-room-1.ogg",
            "bucket": "bucket",
            "key": "recordings/call-room-1.ogg",
        }
    )
    api = FakeApi()
    lifecycle, events = make_lifecycle(api=api, recording=recording)
    lifecycle.on_conversation_item(
        SimpleNamespace(item=SimpleNamespace(role="user", text_content="Hello"))
    )
    lifecycle.on_conversation_item(
        SimpleNamespace(item=SimpleNamespace(role="assistant", text_content="Namaste"))
    )
    lifecycle.on_conversation_item(
        SimpleNamespace(item=SimpleNamespace(role="system", text_content="ignore me"))
    )

    run(lifecycle.shutdown())

    assert recording.stopped is True
    assert recording.closed is True
    assert api.closed is True
    assert len(api.payloads) == 1
    payload = api.payloads[0]
    assert payload["room_name"] == "call-room-1"
    assert payload["from_number"] == "+919000000001"
    assert payload["to_number"] == "+919000000002"
    assert payload["transcript"] == [
        {"role": "user", "text": "Hello", "language": "hi-IN"},
        {"role": "assistant", "text": "Namaste", "language": "hi-IN"},
    ]
    assert payload["recording"]["egress_id"] == "EG_1"
    assert events[-1]["event"] == "call_finalized"
    assert events[-1]["turns"] == 2


def test_lifecycle_retries_finalize_once() -> None:
    api = FakeApi(fail_times=1)
    lifecycle, events = make_lifecycle(api=api)
    run(lifecycle.shutdown())

    assert len(api.payloads) == 1
    assert any(event["event"] == "call_finalize_error" for event in events)
    assert events[-1]["event"] == "call_finalized"


def test_lifecycle_skips_finalize_without_api_key_but_closes_client() -> None:
    api = FakeApi(api_key="")
    lifecycle, events = make_lifecycle(api=api)
    run(lifecycle.shutdown())

    assert api.payloads == []
    assert api.closed is True
    assert events[-1]["event"] == "call_finalize_skipped"


def test_finalize_call_uses_service_key_endpoint() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(202, json={"call_id": "c1", "queued": True})

    client = AgentApiClient(
        "http://api.test",
        "secret-key",
        transport=httpx.MockTransport(handler),
    )
    result = run(client.finalize_call({"room_name": "room-1"}))
    run(client.aclose())

    assert result == {"call_id": "c1", "queued": True}
    assert requests[0].url.path == "/api/v1/agent/calls"
    assert requests[0].headers["X-Service-Key"] == "secret-key"


def test_recording_is_skipped_when_disabled(monkeypatch) -> None:
    events: list[dict[str, Any]] = []
    monkeypatch.setenv("RECORDING_ENABLED", "false")
    recording = RecordingSession(
        "room-1", on_event=lambda event, **fields: events.append({"event": event, **fields})
    )

    assert run(recording.start()) is False
    assert events == [{"event": "recording_skipped", "reason": "disabled"}]
