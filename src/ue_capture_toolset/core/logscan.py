"""Extract recent error lines from an Unreal log."""

from __future__ import annotations

import os
import re
from collections import deque
from pathlib import Path

from .errors import CaptureError

__all__ = ["DEFAULT_LIMIT", "MAX_LINE", "MAX_LOG_CHARS", "read_log_tail", "recent_errors"]

DEFAULT_LIMIT = 20
MAX_LINE = 500
MAX_LOG_CHARS = 8_000_000
_ERROR = re.compile(r"\bError:")


def recent_errors(log_text: str, limit: int = DEFAULT_LIMIT) -> list[str]:
    """Return the last ``limit`` lines containing ``Error:``, in log order.

    Lines are stripped and cut at ``MAX_LINE`` characters.

    Raises:
        CaptureError: ``input_too_large`` when the text exceeds ``MAX_LOG_CHARS``.
    """
    if not isinstance(log_text, str) or len(log_text) > MAX_LOG_CHARS:
        raise CaptureError("input_too_large", f"log text must be at most {MAX_LOG_CHARS} chars")
    if limit <= 0:
        return []
    kept: deque[str] = deque(maxlen=limit)
    for line in log_text.splitlines():
        if _ERROR.search(line):
            kept.append(line.strip()[:MAX_LINE])
    return list(kept)


def read_log_tail(path: str | Path, max_bytes: int = 1_000_000) -> str:
    """Return the last ``max_bytes`` of a log file as text; ``""`` when unreadable."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            data = handle.read(max_bytes)
    except OSError:
        return ""
    return data.decode("utf-8", "replace")
