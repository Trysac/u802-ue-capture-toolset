"""Typed error for the capture toolset."""

from __future__ import annotations

__all__ = ["CaptureError"]

_MAX_MESSAGE = 200


class CaptureError(Exception):
    """Base error of the library.

    ``code`` is a stable machine-readable identifier such as ``invalid_resolution``,
    ``camera_not_found``, ``capture_timeout`` or ``unknown_capture``.
    """

    def __init__(self, code: str, message: str) -> None:
        text = message[:_MAX_MESSAGE]
        super().__init__(f"{code}: {text}")
        self.code = code
        self.message = text
