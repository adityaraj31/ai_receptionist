from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ..config import settings


class LlmError(RuntimeError):
    pass


class LlmNotConfigured(LlmError):
    pass


def _chat_url() -> str:
    base = (settings.llm_base_url or "https://api.openai.com/v1").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _extract_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise LlmError("LLM did not return a JSON object") from None
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LlmError("LLM returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise LlmError("LLM returned a non-object JSON value")
    return payload


async def chat_json(
    system: str,
    user: str,
    *,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    if not settings.llm_api_key:
        raise LlmNotConfigured("LLM_API_KEY is not configured")

    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "max_tokens": max_tokens or settings.call_analysis_max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                _chat_url(),
                json=payload,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            )
    except httpx.HTTPError as exc:
        raise LlmError(f"LLM request failed: {exc!r}") from exc

    if response.status_code >= 400:
        raise LlmError(f"LLM returned HTTP {response.status_code}: {response.text[:300]}")

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LlmError("LLM response did not contain message content") from exc
    if not isinstance(content, str):
        raise LlmError("LLM message content was not text")
    return _extract_json(content)
