from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
import httpx
from botocore.config import Config

from ..config import settings
from ..models import Call

logger = logging.getLogger(__name__)

_AUDIO_SUFFIXES = {".ogg", ".mp3", ".mp4", ".wav", ".m4a"}
_CONTENT_TYPES = {
    ".ogg": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}


class StorageError(RuntimeError):
    pass


def _configured() -> bool:
    if not settings.s3_bucket:
        return False
    has_key = bool(settings.s3_access_key_id)
    has_secret = bool(settings.s3_secret_access_key)
    # Either use explicit keys or let boto3 resolve an IAM task role.
    return has_key == has_secret


def _client():
    addressing_style = "path" if settings.s3_force_path_style else "auto"
    kwargs: dict[str, Any] = {
        "endpoint_url": settings.s3_endpoint_url or None,
        "region_name": settings.s3_region or None,
        "config": Config(signature_version="s3v4", s3={"addressing_style": addressing_style}),
    }
    if settings.s3_access_key_id and settings.s3_secret_access_key:
        kwargs["aws_access_key_id"] = settings.s3_access_key_id
        kwargs["aws_secret_access_key"] = settings.s3_secret_access_key
    return boto3.client("s3", **kwargs)


def _suffix(meta: dict[str, Any]) -> str:
    for value in (meta.get("key"), meta.get("url")):
        if not value:
            continue
        suffix = Path(urlparse(str(value)).path).suffix.lower()
        if suffix in _AUDIO_SUFFIXES:
            return suffix
    return ".ogg"


def _public_url(key: str) -> str:
    if settings.s3_public_base_url:
        return f"{settings.s3_public_base_url.rstrip('/')}/{key.lstrip('/')}"
    return f"s3://{settings.s3_bucket}/{key}"


def _parse_s3_url(value: str) -> tuple[str, str] | None:
    parsed = urlparse(value)
    if parsed.scheme != "s3" or not parsed.netloc:
        return None
    return parsed.netloc, parsed.path.lstrip("/")


async def _download(url: str) -> bytes:
    async with (
        httpx.AsyncClient(
            timeout=settings.s3_timeout_seconds,
            follow_redirects=True,
        ) as client,
        client.stream("GET", url) as response,
    ):
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > settings.recording_max_bytes:
            raise StorageError("recording exceeds RECORDING_MAX_BYTES")
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > settings.recording_max_bytes:
                raise StorageError("recording exceeds RECORDING_MAX_BYTES")
            chunks.append(chunk)
    return b"".join(chunks)


def _copy_object(source_bucket: str, source_key: str, target_key: str) -> None:
    _client().copy_object(
        Bucket=settings.s3_bucket,
        Key=target_key,
        CopySource={"Bucket": source_bucket, "Key": source_key},
    )


def _put_object(target_key: str, content: bytes, content_type: str) -> None:
    _client().put_object(
        Bucket=settings.s3_bucket,
        Key=target_key,
        Body=content,
        ContentType=content_type,
    )


async def persist_recording(
    call: Call,
    meta: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    """Copy the egress recording into the clinic's canonical S3 prefix.

    Returns ``(recording_url, error)``. On failure the original URL is preserved so the
    call is not lost, and the error is recorded on the call for staff/debugging.
    """
    meta = meta or {}
    source_url = str(meta.get("url") or "").strip() or None
    source_bucket = str(meta.get("bucket") or "").strip() or None
    source_key = str(meta.get("key") or "").strip() or None
    if not any((source_url, source_bucket and source_key)):
        return None, None
    if not _configured():
        return source_url, "s3_not_configured"

    suffix = _suffix(meta)
    prefix = (settings.recording_prefix or "recordings").strip("/")
    target_key = f"{prefix}/{call.clinic_id}/{call.id}{suffix}"
    content_type = _CONTENT_TYPES.get(suffix, "application/octet-stream")

    try:
        if source_bucket and source_key:
            if source_bucket != settings.s3_bucket or source_key != target_key:
                await asyncio.to_thread(
                    _copy_object,
                    source_bucket,
                    source_key,
                    target_key,
                )
        elif source_url and source_url.startswith("s3://"):
            parsed = _parse_s3_url(source_url)
            if parsed is None:
                raise StorageError("invalid s3 recording URL")
            await asyncio.to_thread(_copy_object, parsed[0], parsed[1], target_key)
        elif source_url and source_url.startswith(("http://", "https://")):
            content = await _download(source_url)
            await asyncio.to_thread(_put_object, target_key, content, content_type)
        else:
            raise StorageError("recording has no usable source")
    except Exception as exc:
        logger.warning("Recording storage failed for call %s", call.id, exc_info=True)
        return source_url, f"recording_storage_failed: {exc}"[:500]

    return _public_url(target_key), None


def presign_recording_url(url: str, expires_in: int | None = None) -> str:
    parsed = _parse_s3_url(url)
    if parsed is None:
        raise StorageError("invalid s3 recording URL")
    if not _configured():
        raise StorageError("recording storage is not configured")
    bucket, key = parsed
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in or settings.recording_url_ttl_seconds,
    )
