"""HTML parsing: boilerplate removal, main-content extraction, link discovery."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from app.services.crawler.url_utils import normalize
from app.services.text_cleaning import clean

# Structural/boilerplate tags removed before content extraction.
_STRIP_TAGS = [
    "script", "style", "noscript", "template", "svg", "iframe", "form",
    "nav", "header", "footer", "aside", "button", "input", "select",
]
# Heuristic id/class patterns for chrome that isn't in a semantic tag.
_BOILERPLATE_RE = re.compile(
    r"(nav|menu|header|footer|sidebar|breadcrumb|cookie|consent|banner|"
    r"social|share|advert|\bads?\b|popup|modal|subscribe|newsletter|skip-link)",
    re.I,
)
_MAIN_CANDIDATES = ["main", "article", '[role="main"]', "#content", "#main", ".content"]


@dataclass
class Extracted:
    title: str | None
    text: str
    links: set[str] = field(default_factory=set)


def _drop_boilerplate(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()
    # Remove elements whose id/class strongly signals chrome.
    for el in soup.find_all(attrs={"class": _BOILERPLATE_RE}):
        el.decompose()
    for el in soup.find_all(attrs={"id": _BOILERPLATE_RE}):
        el.decompose()
    for el in soup.find_all(attrs={"role": re.compile("navigation|banner|contentinfo", re.I)}):
        el.decompose()


def _title(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        return soup.title.string.strip()[:1024]
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)[:1024]
    return None


def _links(soup: BeautifulSoup, base_url: str) -> set[str]:
    out: set[str] = set()
    for a in soup.find_all("a", href=True):
        norm = normalize(a["href"], base=base_url)
        if norm:
            out.add(norm)
    return out


def extract(html: str, page_url: str) -> Extracted:
    soup = BeautifulSoup(html, "html.parser")

    # Discover links from the full document (nav links are how we find pages).
    title = _title(soup)
    links = _links(soup, page_url)

    # Now strip boilerplate and pick the main content region for text.
    _drop_boilerplate(soup)
    region = None
    for selector in _MAIN_CANDIDATES:
        found = soup.select_one(selector)
        if found and found.get_text(strip=True):
            region = found
            break
    region = region or soup.body or soup

    raw = region.get_text(separator="\n")
    text = clean(raw)
    return Extracted(title=title, text=text, links=links)
