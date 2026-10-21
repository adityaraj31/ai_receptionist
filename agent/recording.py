"""Optional LiveKit room-composite egress recording for completed calls."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from typing import Any

from livekit.api import (
    EncodedFileOutput,
    EncodedFileType,
    LiveKitAPI,
    RoomCompositeEgressRequest,
    S3Upload,
    StopEgressRequest,
)
from livekit.protocol.egress import EgressStatus, ListEgressRequest

logger = logging.getLogger("receptionist.recording")

_TERMINAL_STATUSES = {
    EgressStatus.EGRESS_COMPLETE,
    EgressStatus.EGRESS_FAILED,
    EgressStatus.EGRESS_ABORTED,
    EgressStatus.EGRESS_LIMIT_REACHED,
}
_POLL_INTERVAL_SECONDS = 0.5
_STOP_TIMEOUT_SECONDS = 15.0


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class RecordingSession:
    def __init__(
        self,
        room_name: str,
        *,
        on_event: Callable[..., None],
        enabled: bool | None = None,
    ) -> None:
        self.room_name = room_name
        self._on_event = on_event
        self._enabled = _env_bool("RECORDING_ENABLED", False) if enabled is None else enabled
        self._api: LiveKitAPI | None = None
        self._egress_id: str | None = None
        self.started = False

    def _missing(self) -> list[str]:
        required = (
            "LIVEKIT_URL",
            "LIVEKIT_API_KEY",
            "LIVEKIT_API_SECRET",
            "S3_BUCKET",
            "S3_ACCESS_KEY_ID",
            "S3_SECRET_ACCESS_KEY",
        )
        return [name for name in required if not os.getenv(name, "").strip()]

    async def start(self) -> bool:
        if not self._enabled:
            self._on_event("recording_skipped", reason="disabled")
            return False
        missing = self._missing()
        if missing:
            self._on_event("recording_skipped", reason="missing_config", missing=missing)
            return False

        try:
            self._api = LiveKitAPI()
            prefix = (os.getenv("RECORDING_PREFIX") or "recordings").strip("/")
            path = f"{prefix}/{self.room_name}.ogg"
            request = RoomCompositeEgressRequest(
                room_name=self.room_name,
                audio_only=True,
                file_outputs=[
                    EncodedFileOutput(
                        file_type=EncodedFileType.OGG,
                        filepath=path,
                        s3=S3Upload(
                            bucket=os.getenv("S3_BUCKET", ""),
                            access_key=os.getenv("S3_ACCESS_KEY_ID", ""),
                            secret=os.getenv("S3_SECRET_ACCESS_KEY", ""),
                            region=os.getenv("S3_REGION", ""),
                            endpoint=os.getenv("S3_ENDPOINT_URL", ""),
                            force_path_style=_env_bool("S3_FORCE_PATH_STYLE", False),
                        ),
                    )
                ],
            )
            info = await self._api.egress.start_room_composite_egress(request)
            self._egress_id = info.egress_id
            self.started = True
            self._on_event("recording_started", egress_id=info.egress_id, path=path)
            return True
        except Exception as exc:
            self._on_event("recording_start_error", error=repr(exc))
            await self.close()
            return False

    async def _info(self) -> Any:
        if self._api is None or self._egress_id is None:
            return None
        response = await self._api.egress.list_egress(ListEgressRequest(egress_id=self._egress_id))
        return response.items[0] if response.items else None

    def _metadata(self, info: Any) -> dict[str, Any]:
        result: dict[str, Any] = {"egress_id": self._egress_id}
        files = list(getattr(info, "file_results", []) or [])
        if files:
            file_info = files[0]
            key = str(getattr(file_info, "filename", "") or "")
            location = str(getattr(file_info, "location", "") or "")
            bucket = os.getenv("S3_BUCKET", "")
            result.update(
                {
                    "url": location or (f"s3://{bucket}/{key}" if key else None),
                    "bucket": bucket or None,
                    "key": key or None,
                    "size_bytes": int(getattr(file_info, "size", 0) or 0),
                    "duration_seconds": float(getattr(file_info, "duration", 0) or 0),
                }
            )
        return {key: value for key, value in result.items() if value not in (None, "")}

    async def stop(self) -> dict[str, Any] | None:
        if self._api is None or self._egress_id is None:
            return None

        try:
            await self._api.egress.stop_egress(StopEgressRequest(egress_id=self._egress_id))
        except Exception as exc:
            self._on_event("recording_stop_error", egress_id=self._egress_id, error=repr(exc))

        info = None
        deadline = asyncio.get_running_loop().time() + _STOP_TIMEOUT_SECONDS
        while asyncio.get_running_loop().time() < deadline:
            try:
                info = await self._info()
            except Exception as exc:
                self._on_event("recording_poll_error", egress_id=self._egress_id, error=repr(exc))
                break
            if info is None or getattr(info, "status", None) in _TERMINAL_STATUSES:
                break
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

        if info is None:
            self._on_event("recording_stopped_without_info", egress_id=self._egress_id)
            return None

        metadata = self._metadata(info)
        status = getattr(info, "status", None)
        if status != EgressStatus.EGRESS_COMPLETE:
            error = str(getattr(info, "error", "") or "")
            self._on_event(
                "recording_not_complete",
                egress_id=self._egress_id,
                status=int(status) if status is not None else None,
                error=error,
            )
            return metadata or None

        self._on_event("recording_completed", **metadata)
        return metadata

    async def close(self) -> None:
        if self._api is not None:
            await self._api.aclose()
            self._api = None
