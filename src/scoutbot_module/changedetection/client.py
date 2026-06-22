from __future__ import annotations

import logging
from typing import Any

import httpx

LOG = logging.getLogger("scoutbot.changedetection.client")


# Безопасный парсинг ответа: JSON если возможно, иначе bounded text.
def _safe_parse_response(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text[:1000]


# Оборачивание результатов API в удобный класс
class CDResult:
    def __init__(
        self,
        ok: bool,
        data: Any = None,
        error: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.ok = ok
        self.data = data
        self.error = error
        self.status_code = status_code

    @classmethod
    def success(cls, data: Any = None, status_code: int = 200) -> CDResult:
        return cls(ok=True, data=data, status_code=status_code)

    @classmethod
    def failed(cls, error: str, status_code: int | None = None) -> CDResult:
        return cls(ok=False, error=error, status_code=status_code)

    @property
    def is_degraded(self) -> bool:
        return not self.ok


# Класс: CDClient - тонкий HTTP-клиент для REST API changedetection.io
class CDClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 20,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=httpx.Timeout(timeout),
            headers={"x-api-key": api_key},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str) -> CDResult:
        try:
            resp = await self._client.get(path)
            resp.raise_for_status()
            return CDResult.success(_safe_parse_response(resp), resp.status_code)
        except httpx.HTTPStatusError as exc:
            return CDResult.failed(
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:300]}",
                status_code=exc.response.status_code,
            )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            return CDResult.failed(error=f"Network error: {exc}")

    async def _post(self, path: str, json: dict) -> CDResult:
        try:
            resp = await self._client.post(path, json=json)
            resp.raise_for_status()
            return CDResult.success(_safe_parse_response(resp), resp.status_code)
        except httpx.HTTPStatusError as exc:
            return CDResult.failed(
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:300]}",
                status_code=exc.response.status_code,
            )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            return CDResult.failed(error=f"Network error: {exc}")

    async def _put(self, path: str, json: dict) -> CDResult:
        try:
            resp = await self._client.put(path, json=json)
            resp.raise_for_status()
            return CDResult.success(_safe_parse_response(resp), resp.status_code)
        except httpx.HTTPStatusError as exc:
            return CDResult.failed(
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:300]}",
                status_code=exc.response.status_code,
            )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            return CDResult.failed(error=f"Network error: {exc}")

    async def _delete(self, path: str) -> CDResult:
        try:
            resp = await self._client.delete(path)
            if resp.status_code != 204:
                resp.raise_for_status()
            return CDResult.success(status_code=resp.status_code)
        except httpx.HTTPStatusError as exc:
            return CDResult.failed(
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:300]}",
                status_code=exc.response.status_code,
            )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            return CDResult.failed(error=f"Network error: {exc}")

    async def health(self) -> CDResult:
        return await self._get("/api/v1/systeminfo")

    async def system_info(self) -> CDResult:
        return await self._get("/api/v1/systeminfo")

    async def list_watches(self) -> CDResult:
        return await self._get("/api/v1/watch")

    async def get_watch(self, uuid: str) -> CDResult:
        return await self._get(f"/api/v1/watch/{uuid}")

    async def create_watch(self, payload: dict) -> CDResult:
        return await self._post("/api/v1/watch", json=payload)

    async def update_watch(self, uuid: str, payload: dict) -> CDResult:
        return await self._put(f"/api/v1/watch/{uuid}", json=payload)

    async def delete_watch(self, uuid: str) -> CDResult:
        return await self._delete(f"/api/v1/watch/{uuid}")

    async def check_watch(self, uuid: str) -> CDResult:
        return await self._get(f"/api/v1/watch/{uuid}/history")
