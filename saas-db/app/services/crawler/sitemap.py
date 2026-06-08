"""sitemap.xml discovery and parsing (handles sitemap-index files)."""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET

import httpx

from app.core.logging import get_logger
from app.services.crawler.fetcher import fetch_raw
from app.services.crawler.url_utils import normalize

logger = get_logger("app.crawler.sitemap")

# Strip XML namespaces so tag lookups are simple.
_NS_RE = re.compile(r"\{.*?\}")


def _localname(tag: str) -> str:
    return _NS_RE.sub("", tag).lower()


async def collect_urls(
    client: httpx.AsyncClient, sitemap_url: str, *, max_urls: int, _depth: int = 0
) -> list[str]:
    """Return page URLs from a sitemap or sitemap index (recurses once-deep)."""
    if _depth > 3:
        return []
    raw = await fetch_raw(client, sitemap_url)
    if not raw:
        return []
    try:
        root = ET.fromstring(raw.encode("utf-8"))
    except ET.ParseError as exc:
        logger.warning("Bad sitemap XML at %s: %s", sitemap_url, exc)
        return []

    tag = _localname(root.tag)
    urls: list[str] = []

    if tag == "sitemapindex":
        for sm in root:
            loc = _first_loc(sm)
            if loc:
                child = normalize(loc)
                if child:
                    urls.extend(
                        await collect_urls(
                            client, child, max_urls=max_urls, _depth=_depth + 1
                        )
                    )
                    if len(urls) >= max_urls:
                        break
    else:  # urlset
        for url_el in root:
            loc = _first_loc(url_el)
            norm = normalize(loc) if loc else None
            if norm:
                urls.append(norm)
                if len(urls) >= max_urls:
                    break

    # De-dupe, preserve order.
    seen: set[str] = set()
    deduped = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped[:max_urls]


def _first_loc(element) -> str | None:
    for child in element:
        if _localname(child.tag) == "loc" and child.text:
            return child.text.strip()
    return None
