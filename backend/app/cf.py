"""Codeforces public API client.

Rate limit: at most 1 call per 2 seconds, enforced process-wide with an
asyncio lock + timestamp (single Render instance, so in-memory is enough).
Retries use exponential backoff; a FAILED response is never hammered.
"""

import asyncio
import os
import time
from typing import Any

import httpx

from .config import CF_API_BASE, CF_MIN_INTERVAL_S


class CFError(Exception):
    pass


class CFClient:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._last_call = 0.0
        self._problemset_cache: tuple[float, list[dict]] | None = None
        self._contest_cache: tuple[float, list[dict]] | None = None

    async def _get(
        self, path: str, params: dict | None = None, retries: int = 3
    ) -> Any:
        async with self._lock:
            wait = CF_MIN_INTERVAL_S - (time.monotonic() - self._last_call)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call = time.monotonic()
        url = f"{CF_API_BASE}{path}"
        backoff = 2.0
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                # Proxy is passed explicitly: httpx chokes parsing this VM's
                # NO_PROXY list (bare IPv6 entries) when reading env itself,
                # and direct TLS fails because egress requires the proxy.
                # trust_env=False stops httpx from re-parsing the env.
                proxy = (
                    os.environ.get("https_proxy")
                    or os.environ.get("HTTPS_PROXY")
                    or os.environ.get("http_proxy")
                    or None
                )
                # System CA bundle (includes the egress proxy's CA on this VM;
                # on Render it is the stock Debian bundle).
                bundle = "/etc/ssl/certs/ca-certificates.crt"
                verify = bundle if os.path.exists(bundle) else True
                async with httpx.AsyncClient(
                    timeout=30, trust_env=False, proxy=proxy, verify=verify
                ) as client:
                    resp = await client.get(url, params=params or {})
                data = resp.json()
                if data.get("status") == "OK":
                    return data["result"]
                # "FAILED" — e.g. call limit exceeded, bad handle. Back off.
                last_err = CFError(data.get("comment", "Codeforces API failed"))
            except (httpx.HTTPError, ValueError) as exc:
                last_err = CFError(str(exc))
            if attempt < retries - 1:
                await asyncio.sleep(backoff)
                backoff *= 2
        raise last_err or CFError("Codeforces API failed")

    async def verify_handle(self, handle: str) -> dict:
        """Returns user info; raises CFError for a bad handle."""
        result = await self._get("/user.info", {"handles": handle})
        if not result:
            raise CFError("Handle not found on Codeforces")
        return result[0]

    async def user_status(
        self, handle: str, start_from: int = 1, count: int = 1000
    ) -> list[dict]:
        return await self._get(
            "/user.status", {"handle": handle, "from": start_from, "count": count}
        )

    async def user_rating(self, handle: str) -> list[dict]:
        return await self._get("/user.rating", {"handle": handle})

    async def problemset(self) -> list[dict]:
        """All problems, cached in memory for 1 hour (it changes rarely)."""
        now = time.monotonic()
        if self._problemset_cache and now - self._problemset_cache[0] < 3600:
            return self._problemset_cache[1]
        result = await self._get("/problemset.problems")
        problems = result.get("problems", [])
        self._problemset_cache = (now, problems)
        return problems

    async def contest_list(self) -> list[dict]:
        """All contests (id, name, phase, ...), cached in memory for
        1 hour. Names change rarely; used to label post-mortems."""
        now = time.monotonic()
        if self._contest_cache and now - self._contest_cache[0] < 3600:
            return self._contest_cache[1]
        result = await self._get("/contest.list")
        self._contest_cache = (now, result)
        return result


cf = CFClient()
