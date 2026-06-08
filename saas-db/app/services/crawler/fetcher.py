"""Resilient async HTTP fetching for the crawler."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.crawler.fetch")


@dataclass
class FetchResult:
    url: str          # final URL after redirects
    status: int
    content_type: str
    text: str | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300


_RETRYABLE = {429, 500, 502, 503, 504}


async def fetch(client: httpx.AsyncClient, url: str) -> FetchResult:
    """GET a URL with retries/backoff. Only returns text for HTML responses."""
    attempt = 0
    last_err = "unknown error"
    while attempt <= settings.CRAWLER_RETRY_MAX:
        attempt += 1
        try:
            resp = await client.get(url, follow_redirects=True)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            await _backoff(attempt)
            continue

        if resp.status_code in _RETRYABLE:
            last_err = f"HTTP {resp.status_code}"
            await _backoff(attempt)
            continue

        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        final_url = str(resp.url)
        if resp.status_code >= 400:
            return FetchResult(final_url, resp.status_code, ctype, None,
                               error=f"HTTP {resp.status_code}")
        if "html" not in ctype and ctype not in ("application/xhtml+xml", ""):
            return FetchResult(final_url, resp.status_code, ctype, None,
                               error=f"non-HTML content-type: {ctype or 'unknown'}")

        # Size guard (also enforced by max bytes on read).
        body = resp.content[: settings.CRAWLER_MAX_BYTES_PER_PAGE]
        try:
            text = body.decode(resp.encoding or "utf-8", errors="replace")
        except (LookupError, TypeError):
            text = body.decode("utf-8", errors="replace")
        return FetchResult(final_url, resp.status_code, ctype, text)

    return FetchResult(url, 0, "", None, error=f"failed after retries: {last_err}")


async def fetch_raw(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch raw text (used for robots.txt / sitemaps); tolerant of failure."""
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except (httpx.TimeoutException, httpx.TransportError):
        return None
    return None


async def _backoff(attempt: int) -> None:
    await asyncio.sleep(settings.CRAWLER_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": settings.CRAWLER_USER_AGENT},
        timeout=settings.CRAWLER_TIMEOUT_SECONDS,
        max_redirects=5,
    )
