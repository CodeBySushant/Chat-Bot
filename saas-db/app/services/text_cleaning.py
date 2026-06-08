"""Text normalization applied before chunking."""
from __future__ import annotations

import re
import unicodedata

# Control chars except tab/newline.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# 3+ newlines -> paragraph break.
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
# Spaces/tabs runs -> single space.
_HSPACE_RE = re.compile(r"[ \t]+")
# Word split across a line break by a hyphen: "exam-\nple" -> "example".
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")
# Trailing spaces per line.
_TRAILING_RE = re.compile(r"[ \t]+\n")


def clean(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)
    text = _CONTROL_RE.sub("", text)
    text = _TRAILING_RE.sub("\n", text)
    text = _HSPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()
