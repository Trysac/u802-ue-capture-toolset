"""Resolution parsing."""

from __future__ import annotations

import re

from .errors import CaptureError

__all__ = ["MAX_DIMENSION", "MAX_TEXT_LEN", "parse_resolution"]

MAX_TEXT_LEN = 32
MAX_DIMENSION = 16384
_PATTERN = re.compile(r"([0-9]{1,5})[xX]([0-9]{1,5})")


def parse_resolution(text: str) -> tuple[int, int]:
    """Parse ``WIDTHxHEIGHT`` into ``(width, height)``.

    Raises:
        CaptureError: code ``invalid_resolution`` for malformed text, zero or too large values.
    """
    if not isinstance(text, str) or len(text) > MAX_TEXT_LEN:
        raise CaptureError("invalid_resolution", "resolution must be a short string")
    match = _PATTERN.fullmatch(text.strip())
    if match is None:
        raise CaptureError("invalid_resolution", f"cannot parse resolution {text[:40]!r}")
    width, height = int(match.group(1)), int(match.group(2))
    if not (1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION):
        raise CaptureError("invalid_resolution", f"dimensions out of range: {width}x{height}")
    return width, height
