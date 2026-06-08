"""Upload validation: extension allowlist, content sniffing, size limit."""
from __future__ import annotations

import os

from app.core.config import settings
from app.core.exceptions import ValidationFailed

# extension -> (kind, canonical mime)
SUPPORTED: dict[str, tuple[str, str]] = {
    "pdf": ("pdf", "application/pdf"),
    "docx": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "txt": ("txt", "text/plain"),
    "md": ("md", "text/markdown"),
    "markdown": ("md", "text/markdown"),
    "csv": ("csv", "text/csv"),
}


def _ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lstrip(".").lower()


def _looks_like(kind: str, data: bytes) -> bool:
    """Magic-byte sanity check for binary formats; text formats pass through."""
    if kind == "pdf":
        return data[:5] == b"%PDF-"
    if kind == "docx":
        # docx is a zip (PK\x03\x04) container.
        return data[:4] == b"PK\x03\x04"
    if kind in {"txt", "md", "csv"}:
        return True
    return False


def validate_upload(filename: str | None, data: bytes) -> tuple[str, str]:
    """Return (kind, mime) or raise ValidationFailed."""
    if not filename:
        raise ValidationFailed("A filename is required")
    if not data:
        raise ValidationFailed("Uploaded file is empty")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise ValidationFailed(
            f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit",
            details={"size": len(data), "max_bytes": max_bytes},
        )

    ext = _ext(filename)
    if ext not in SUPPORTED:
        raise ValidationFailed(
            f"Unsupported file type '.{ext}'",
            details={"supported": sorted({k for k in SUPPORTED})},
        )

    kind, mime = SUPPORTED[ext]
    if not _looks_like(kind, data):
        raise ValidationFailed(
            f"File content does not match its .{ext} extension"
        )
    return kind, mime
