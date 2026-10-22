#!/usr/bin/env python3
"""Run concurrent synthetic calls against a deployed LiveKit agent worker.

The script creates N LiveKit rooms, explicitly dispatches the receptionist agent to
each room, joins as a caller, and waits for the agent's first audio frame. That
exercises room creation, dispatch, session startup, STT/TTS initialisation, and the
worker's HTTP/proc pool under load.

Without ``--audio`` the caller stays silent. That is a useful smoke test, but it only
measures the greeting path. Pass a PCM WAV of a real caller (for example a 15-30 second
Hindi/English booking conversation) to exercise STT, the LLM tools, and TTS:

    cd agent
    uv run python scripts/load_test_calls.py --calls 25 --audio /tmp/caller.wav

Environment is read from agent/.env and the repo-root .env, or the usual LIVEKIT_*
variables. The agent must already be running and registered under LIVEKIT_AGENT_NAME.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import statistics
import sys
import time
import uuid
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from livekit import rtc
from livekit.api import (
    AccessToken,
    CreateRoomRequest,
    DeleteRoomRequest,
    LiveKitAPI,
    RoomAgentDispatch,
    VideoGrants,
)

AGENT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = AGENT_DIR.parent
load_dotenv(AGENT_DIR / ".env")
load_dotenv(ROOT_DIR / ".env")


@dataclass
class CallResult:
    index: int
    room: str
    ok: bool
    connected_ms: float | None = None
    first_audio_ms: float | None = None
    held_seconds: float | None = None
    error: str | None = None


def _http_url(ws_url: str) -> str:
    if ws_url.startswith("wss://"):
        return "https://" + ws_url.removeprefix("wss://")
    if ws_url.startswith("ws://"):
        return "http://" + ws_url.removeprefix("ws://")
    return ws_url.rstrip("/")


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return round(ordered[index], 1)


class WavCaller:
    """Publish a mono/stereo 16-bit PCM WAV on a loop at real-time pace."""

    def __init__(self, path: Path) -> None:
        with wave.open(str(path), "rb") as wav:
            if wav.getsampwidth() != 2:
                raise ValueError("caller WAV must be 16-bit PCM")
            if wav.getnchannels() not in (1, 2):
                raise ValueError("caller WAV must have 1 or 2 channels")
            self.sample_rate = wav.getframerate()
            self.num_channels = wav.getnchannels()
            self.frames = wav.readframes(wav.getnframes())
        if not self.frames:
            raise ValueError("caller WAV is empty")

        self.samples_per_frame = max(1, int(self.sample_rate * 0.02))
        self.bytes_per_frame = self.samples_per_frame * self.num_channels * 2
        self._source: rtc.AudioSource | None = None

    async def start(self, room: rtc.Room) -> None:
        self._source = rtc.AudioSource(self.sample_rate, self.num_channels)
        track = rtc.LocalAudioTrack.create_audio_track("caller", self._source)
        await room.local_participant.publish_track(
            track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        )

    async def pump(self, stop: asyncio.Event) -> None:
        if self._source is None:
            return
        offset = 0
        while not stop.is_set():
            chunk = self.frames[offset : offset + self.bytes_per_frame]
            if len(chunk) < self.bytes_per_frame:
                offset = 0
                chunk = self.frames[: self.bytes_per_frame]
            if len(chunk) < self.bytes_per_frame:
                break
            frame = rtc.AudioFrame(
                chunk,
                sample_rate=self.sample_rate,
                num_channels=self.num_channels,
                samples_per_channel=self.samples_per_frame,
            )
            self._source.capture_frame(frame)
            offset += self.bytes_per_frame
            await asyncio.sleep(0.02)

    async def close(self) -> None:
        if self._source is not None:
            await self._source.aclose()
            self._source = None


async def run_one_call(
    *,
    api: LiveKitAPI,
    index: int,
    livekit_url: str,
    api_key: str,
    api_secret: str,
    agent_name: str,
    duration: float,
    join_timeout: float,
    audio_path: Path | None,
    keep_rooms: bool,
) -> CallResult:
    room_name = f"loadtest-{index:03d}-{uuid.uuid4().hex[:8]}"
    result = CallResult(index=index, room=room_name, ok=False)
    room = rtc.Room()
    traffic = WavCaller(audio_path) if audio_path else None
    publisher_stop = asyncio.Event()
    audio_tasks: list[asyncio.Task[None]] = []
    first_audio = asyncio.Event()
    started = time.perf_counter()

    def on_track_subscribed(
        track: rtc.Track,
        _publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        if participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            return

        async def consume() -> None:
            stream = rtc.AudioStream(track)
            try:
                async for _frame in stream:
                    first_audio.set()
                    return
            finally:
                await stream.aclose()

        audio_tasks.append(asyncio.create_task(consume()))

    room.on("track_subscribed", on_track_subscribed)

    try:
        await asyncio.wait_for(
            api.room.create_room(
                CreateRoomRequest(
                    name=room_name,
                    empty_timeout=max(120, int(duration) + 120),
                    departure_timeout=20,
                    agents=[RoomAgentDispatch(agent_name=agent_name)],
                )
            ),
            timeout=join_timeout,
        )

        token = (
            AccessToken(api_key, api_secret)
            .with_identity(f"loadtest-caller-{index}")
            .with_name(f"Load test caller {index}")
            .with_grants(
                VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                )
            )
            .to_jwt()
        )
        await asyncio.wait_for(room.connect(livekit_url, token), timeout=join_timeout)
        result.connected_ms = round((time.perf_counter() - started) * 1000, 1)

        await asyncio.wait_for(first_audio.wait(), timeout=join_timeout)
        result.first_audio_ms = round((time.perf_counter() - started) * 1000, 1)

        if traffic is not None:
            await traffic.start(room)
            audio_tasks.append(asyncio.create_task(traffic.pump(publisher_stop)))

        held_started = time.perf_counter()
        await asyncio.sleep(duration)
        result.held_seconds = round(time.perf_counter() - held_started, 1)
        result.ok = True
    except Exception as exc:  # noqa: BLE001 - report every call failure
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        publisher_stop.set()
        for task in audio_tasks:
            task.cancel()
        await asyncio.gather(*audio_tasks, return_exceptions=True)
        if traffic is not None:
            await traffic.close()
        await room.disconnect()
        if not keep_rooms:
            with contextlib.suppress(Exception):
                await api.room.delete_room(DeleteRoomRequest(room=room_name))
    return result


def _summary(results: list[CallResult]) -> dict[str, Any]:
    connected = [r.connected_ms for r in results if r.connected_ms is not None]
    first_audio = [r.first_audio_ms for r in results if r.first_audio_ms is not None]
    failures = sum(not result.ok for result in results)
    return {
        "calls": len(results),
        "ok": len(results) - failures,
        "failed": failures,
        "connected_ms_p50": _percentile(connected, 0.50),
        "connected_ms_p95": _percentile(connected, 0.95),
        "first_audio_ms_p50": _percentile(first_audio, 0.50),
        "first_audio_ms_p95": _percentile(first_audio, 0.95),
        "first_audio_ms_mean": round(statistics.fmean(first_audio), 1) if first_audio else None,
    }


async def main(args: argparse.Namespace) -> int:
    livekit_url = os.getenv("LIVEKIT_URL", "").strip()
    api_key = os.getenv("LIVEKIT_API_KEY", "").strip()
    api_secret = os.getenv("LIVEKIT_API_SECRET", "").strip()
    agent_name = args.agent_name or os.getenv("LIVEKIT_AGENT_NAME", "ai-receptionist")
    missing = [
        name
        for name, value in (
            ("LIVEKIT_URL", livekit_url),
            ("LIVEKIT_API_KEY", api_key),
            ("LIVEKIT_API_SECRET", api_secret),
        )
        if not value
    ]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")

    audio_path = Path(args.audio).expanduser().resolve() if args.audio else None
    if audio_path is not None and not audio_path.is_file():
        raise SystemExit(f"Audio file not found: {audio_path}")

    api = LiveKitAPI(_http_url(livekit_url), api_key, api_secret)
    started = time.perf_counter()
    try:
        tasks: list[asyncio.Task[CallResult]] = []
        for index in range(args.calls):
            tasks.append(
                asyncio.create_task(
                    run_one_call(
                        api=api,
                        index=index + 1,
                        livekit_url=livekit_url,
                        api_key=api_key,
                        api_secret=api_secret,
                        agent_name=agent_name,
                        duration=args.duration,
                        join_timeout=args.join_timeout,
                        audio_path=audio_path,
                        keep_rooms=args.keep_rooms,
                    )
                )
            )
            if args.start_interval > 0 and index < args.calls - 1:
                await asyncio.sleep(args.start_interval)

        results = await asyncio.gather(*tasks)
    finally:
        await api.aclose()

    elapsed = round(time.perf_counter() - started, 1)
    summary = _summary(results)
    summary["elapsed_seconds"] = elapsed
    summary["calls_per_second_started"] = round(args.calls / elapsed, 2) if elapsed else None
    report = {"summary": summary, "calls": [asdict(result) for result in results]}

    print(json.dumps(summary, indent=2))
    for result in results:
        status = "ok" if result.ok else "FAIL"
        print(
            f"[{status:4}] {result.room} "
            f"connect={result.connected_ms}ms first_audio={result.first_audio_ms}ms"
            + (f" error={result.error}" if result.error else ""),
            file=sys.stderr,
        )

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")

    return 0 if summary["failed"] == 0 or args.allow_failures else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls", type=int, default=10, help="concurrent calls to start")
    parser.add_argument("--duration", type=float, default=20, help="seconds to hold each call")
    parser.add_argument(
        "--start-interval",
        type=float,
        default=0,
        help="seconds between call starts (0 starts all at once)",
    )
    parser.add_argument(
        "--join-timeout",
        type=float,
        default=45,
        help="seconds to wait for room join / first agent audio",
    )
    parser.add_argument("--audio", help="16-bit PCM WAV of caller speech (optional)")
    parser.add_argument("--agent-name", help="defaults to LIVEKIT_AGENT_NAME")
    parser.add_argument("--output", help="write the full JSON report to this path")
    parser.add_argument("--keep-rooms", action="store_true", help="do not delete rooms on exit")
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="return exit 0 even when some calls fail",
    )
    return parser


if __name__ == "__main__":
    parsed = _parser().parse_args()
    if parsed.calls < 1:
        raise SystemExit("--calls must be >= 1")
    if parsed.duration < 1:
        raise SystemExit("--duration must be >= 1")
    try:
        raise SystemExit(asyncio.run(main(parsed)))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
