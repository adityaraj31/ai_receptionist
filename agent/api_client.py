"""HTTP client for the clinic API used by the voice agent.

Every request is clinic-scoped by the ``X-Service-Key`` header. Errors are split into
"unavailable" (timeouts, network, 5xx) and "rejected" (4xx with a detail message) so the
tools can choose a natural fallback line instead of raising through the call.
"""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_TIMEOUT_SECONDS = 8.0


class AgentApiError(Exception):
    """Base class for agent API failures."""


class AgentApiUnavailable(AgentApiError):
    """The API could not be reached or returned a server error."""


class AgentApiRejected(AgentApiError):
    """The API rejected the request (4xx)."""

    def __init__(self, status_code: int, detail: str, payload: Any = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.payload = payload


class AgentApiClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 3.0)),
            transport=transport,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {"X-Service-Key": self.api_key}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(),
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise AgentApiUnavailable(f"{method} {path} failed: {exc!r}") from exc

        if response.status_code >= 500:
            raise AgentApiUnavailable(f"{method} {path} returned {response.status_code}")

        if response.status_code >= 400:
            detail, payload = _error_detail(response)
            raise AgentApiRejected(response.status_code, detail, payload)

        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise AgentApiUnavailable(f"{method} {path} returned invalid JSON") from exc

    async def get_clinic_config(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/agent/clinic-config")

    async def get_appointment(self, appointment_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/appointments/{appointment_id}")

    async def free_slots(self, doctor_id: str, date: str) -> list[dict[str, Any]]:
        return await self._request(
            "GET",
            f"/api/v1/doctors/{doctor_id}/free-slots",
            params={"date": date},
        )

    async def book_appointment(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/appointments", json=payload)

    async def reschedule_appointment(
        self,
        appointment_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/api/v1/appointments/{appointment_id}/reschedule",
            json=payload,
        )

    async def cancel_appointment(self, appointment_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/appointments/{appointment_id}/cancel",
        )

    async def search_faq(self, query: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/agent/faq/search",
            json={"query": query},
        )

    async def create_callback(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/agent/callbacks",
            json=payload,
        )

    async def send_confirmation(
        self,
        appointment_id: str,
        channel: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/agent/appointments/{appointment_id}/confirmation",
            json={"channel": channel},
        )

    async def finalize_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/agent/calls",
            json=payload,
        )


def _error_detail(response: httpx.Response) -> tuple[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}", None

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail, payload
        if detail is not None:
            return str(detail), payload
    return f"HTTP {response.status_code}", payload
