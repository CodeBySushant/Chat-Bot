"""URL normalization and scoping helpers for the crawler."""
from __future__ import annotations

from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

# Things we never want to enqueue as crawlable pages.
_SKIP_SCHEMES = {"mailto", "tel", "javascript", "data", "ftp"}
_NON_HTML_EXT = (
    ".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".mp4",
    ".mp3", ".avi", ".mov", ".css", ".js", ".ico", ".woff", ".woff2", ".ttf",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".gz", ".tar", ".rar",
)


def normalize(url: str, base: str | None = None) -> str | None:
    """Resolve relative URLs against base, drop fragments, normalize.

    Returns None for non-crawlable schemes or obvious binary assets.
    """
    if not url:
        return None
    url = url.strip()
    if base:
        url = urljoin(base, url)
    url, _frag = urldefrag(url)
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme not in ("http", "https"):
        return None
    if parsed.scheme.lower() in _SKIP_SCHEMES:
        return None
    if not parsed.netloc:
        return None
    path = parsed.path or "/"
    if path.lower().endswith(_NON_HTML_EXT):
        return None
    # Drop default ports, lowercase host, strip trailing slash (except root).
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif netloc.endswith(":443"):
        netloc = netloc[:-4]
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), netloc, path, "", parsed.query, ""))


def registrable_host(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0]


def same_site(url: str, root: str) -> bool:
    """Same host, or a subdomain of the root host."""
    h, r = registrable_host(url), registrable_host(root)
    return h == r or h.endswith("." + r)
