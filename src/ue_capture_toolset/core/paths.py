"""Unique, time-sortable capture paths under a project's Saved folder."""

from __future__ import annotations

import re
import threading
import unicodedata
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from .errors import CaptureError

__all__ = [
    "MAX_COLLISIONS",
    "MAX_LABEL_LEN",
    "MAX_RESERVED",
    "MAX_SLUG_LEN",
    "capture_path",
    "slugify",
]

MAX_LABEL_LEN = 200
MAX_SLUG_LEN = 40
MAX_COLLISIONS = 9999
MAX_RESERVED = 4096

_reserved: OrderedDict[str, None] = OrderedDict()
_lock = threading.Lock()


def slugify(label: str) -> str:
    """Return a lower-case ``[a-z0-9-]`` slug of at most ``MAX_SLUG_LEN`` characters.

    Raises:
        CaptureError: code ``invalid_label`` when the label is not text or too long.
    """
    if not isinstance(label, str) or len(label) > MAX_LABEL_LEN:
        raise CaptureError("invalid_label", f"label must be text of at most {MAX_LABEL_LEN} chars")
    folded = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")[:MAX_SLUG_LEN].strip("-")
    return slug or "capture"


def capture_path(
    saved_dir: str | Path,
    label: str = "capture",
    at: datetime | None = None,
) -> Path:
    """Return ``<saved_dir>/Captures/<YYYY-MM-DD>/<HHMMSS>-<slug>.png``.

    A name already on disk or already handed out by this process gets a ``~002``-style suffix,
    which sorts after the plain name, so names stay unique and time-sortable. Nothing is created.

    Raises:
        CaptureError: ``invalid_label`` or ``too_many_captures``.
    """
    slug = slugify(label)
    when = at if at is not None else datetime.now()
    directory = Path(saved_dir) / "Captures" / when.strftime("%Y-%m-%d")
    stem = f"{when.strftime('%H%M%S')}-{slug}"
    with _lock:
        for number in range(1, MAX_COLLISIONS + 1):
            name = f"{stem}.png" if number == 1 else f"{stem}~{number:03d}.png"
            candidate = directory / name
            key = str(candidate)
            if key in _reserved or candidate.exists():
                continue
            _reserved[key] = None
            while len(_reserved) > MAX_RESERVED:
                _reserved.popitem(last=False)
            return candidate
    raise CaptureError("too_many_captures", "too many captures with the same name and second")
