"""Shared HTTP client for web modules: honoring settings (proxy, TLS,
timeout, rate-limit) and safe defaults."""
from __future__ import annotations

import asyncio
import time

import httpx

from ... import config


def make_client(base_url: str = "", cookies: dict | None = None,
                headers: dict | None = None) -> httpx.AsyncClient:
    s = config.load_settings()
    proxies = s.get("proxy") or None
    all_headers = {"User-Agent": "CTFSuite/0.1 (+local pentest tool)"}
    if headers:
        all_headers.update(headers)
    return httpx.AsyncClient(
        base_url=base_url,
        cookies=cookies or {},
        headers=all_headers,
        timeout=float(s.get("http_timeout", 10)),
        verify=bool(s.get("verify_tls", False)),
        proxy=proxies,
        follow_redirects=False,
    )


class RateLimiter:
    """Simple min-interval rate limiter."""

    def __init__(self, delay: float) -> None:
        self.delay = max(0.0, float(delay))
        self._last = 0.0

    async def wait(self) -> None:
        if self.delay <= 0:
            return
        now = time.monotonic()
        wait_for = self._last + self.delay - now
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        self._last = time.monotonic()


def success_heuristics(baseline: httpx.Response, resp: httpx.Response) -> tuple[bool, str]:
    """Compare a login attempt response to the baseline; return (success, reason)."""
    if resp.status_code in (301, 302, 303, 307, 308) and \
            resp.status_code != baseline.status_code:
        loc = resp.headers.get("location", "")
        if "error" not in loc.lower() and "denied" not in loc.lower():
            return True, f"redirect beda: {resp.status_code} -> {loc}"
    if "set-cookie" in {k.lower() for k in resp.headers} and \
            "set-cookie" not in {k.lower() for k in baseline.headers}:
        return True, "server memberi Set-Cookie (baseline tidak)"
    bl, rl = len(baseline.content), len(resp.content)
    if baseline.status_code == resp.status_code:
        if abs(bl - rl) > max(bl * 0.2, 40):
            return True, f"panjang response beda signifikan ({bl} vs {rl})"
    return False, "mirip baseline (gagal)"


DEFAULT_UA = "CTFSuite/0.1"
