"""Text extraction per file type.

Returns a list of ``Segment(text, page_number)``. PDFs yield one segment per
page (page numbers preserved); other formats yield a single segment with
``page_number=None``. Extraction never raises for empty content -- it returns
empty segments and the caller decides how to handle a document with no text.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import docx
from pypdf import PdfReader

from app.core.exceptions import ValidationFailed


@dataclass
class Segment:
    text: str
    page_number: int | None = None


def _extract_pdf(data: bytes) -> list[Segment]:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # malformed PDF
        raise ValidationFailed(f"Could not read PDF: {exc}") from exc
    segments: list[Segment] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            segments.append(Segment(text=text, page_number=i))
    return segments


def _extract_docx(data: bytes) -> list[Segment]:
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ValidationFailed(f"Could not read DOCX: {exc}") from exc
    parts: list[str] = [p.text for p in document.paragraphs if p.text.strip()]
    # Include table cell text, row by row.
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return [Segment(text="\n".join(parts))]


def _extract_text(data: bytes) -> list[Segment]:
    text = data.decode("utf-8", errors="replace")
    return [Segment(text=text)]


def _extract_csv(data: bytes) -> list[Segment]:
    text = data.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [Segment(text="")]
    header = rows[0]
    lines: list[str] = []
    # Linearize each row as "col: value" pairs so embeddings see field context.
    for row in rows[1:]:
        pairs = [
            f"{header[i] if i < len(header) else f'col{i}'}: {val}"
            for i, val in enumerate(row)
        ]
        lines.append("; ".join(pairs))
    if not lines:  # header-only file
        lines = ["; ".join(header)]
    return [Segment(text="\n".join(lines))]


_EXTRACTORS = {
    "pdf": _extract_pdf,
    "docx": _extract_docx,
    "txt": _extract_text,
    "md": _extract_text,
    "csv": _extract_csv,
}


def extract(kind: str, data: bytes) -> list[Segment]:
    extractor = _EXTRACTORS.get(kind)
    if extractor is None:
        raise ValidationFailed(f"Unsupported document type: {kind}")
    return extractor(data)
