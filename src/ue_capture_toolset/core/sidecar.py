"""JSON sidecar describing one capture."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import CaptureError

__all__ = [
    "MAX_PROVENANCE",
    "MAX_SIDECAR_BYTES",
    "Sidecar",
    "load_sidecar",
    "read_provenance",
    "sidecar_path_for",
    "write_sidecar",
]

SCHEMA_VERSION = 1
MAX_SIDECAR_BYTES = 1_000_000
MAX_PROVENANCE = 100
MAX_QUALITY = 64
MAX_STR = 500
MAX_DIMENSION = 16384


def _bad(message: str) -> CaptureError:
    return CaptureError("invalid_sidecar", message)


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or len(value) > MAX_STR:
        raise _bad(f"field {key!r} must be text of at most {MAX_STR} characters")
    return value


def _triple(value: Any, name: str) -> tuple[float, float, float]:
    if not isinstance(value, list | tuple) or len(value) != 3:
        raise _bad(f"{name} must hold three numbers")
    if not all(_is_number(v) for v in value):
        raise _bad(f"{name} must hold finite numbers")
    return (float(value[0]), float(value[1]), float(value[2]))


def _resolution(value: Any) -> tuple[int, int]:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise _bad("resolution must hold two integers")
    if not all(_is_int(v) and 1 <= v <= MAX_DIMENSION for v in value):
        raise _bad("resolution values out of range")
    return (int(value[0]), int(value[1]))


def _quality(value: Any) -> dict[str, int]:
    if not isinstance(value, dict) or len(value) > MAX_QUALITY:
        raise _bad("quality must be a small object")
    for key, item in value.items():
        if not isinstance(key, str) or len(key) > MAX_STR or not _is_int(item):
            raise _bad("quality entries must map text to integers")
    return dict(value)


def _provenance(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or len(value) > MAX_PROVENANCE:
        raise _bad("provenance must be a short list")
    if not all(isinstance(item, dict) for item in value):
        raise _bad("provenance entries must be objects")
    return tuple(value)


@dataclass(frozen=True)
class Sidecar:
    """Context of one capture. ``image`` is relative to the project's Saved folder."""

    image: str
    label: str
    map: str
    camera: str
    location: tuple[float, float, float]
    rotation: tuple[float, float, float]
    resolution: tuple[int, int]
    quality: dict[str, int]
    git_commit: str | None
    captured_at: str
    provenance: tuple[dict[str, Any], ...] = ()

    @property
    def summary(self) -> str:
        """One-line description."""
        return f"{self.label} on {self.map} via {self.camera} at {self.captured_at}"

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-serialisable form (rotation is pitch, yaw, roll)."""
        return {
            "version": SCHEMA_VERSION,
            "image": self.image,
            "label": self.label,
            "map": self.map,
            "camera": self.camera,
            "location": list(self.location),
            "rotation": list(self.rotation),
            "resolution": list(self.resolution),
            "quality": dict(sorted(self.quality.items())),
            "git_commit": self.git_commit,
            "captured_at": self.captured_at,
            "provenance": list(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: Any) -> Sidecar:
        """Validate ``data`` and build a sidecar.

        Raises:
            CaptureError: code ``invalid_sidecar`` on any malformed field.
        """
        if not isinstance(data, dict):
            raise _bad("sidecar must be a JSON object")
        commit = data.get("git_commit")
        if commit is not None and (not isinstance(commit, str) or len(commit) > 64):
            raise _bad("git_commit must be text or null")
        return cls(
            image=_text(data, "image"),
            label=_text(data, "label"),
            map=_text(data, "map"),
            camera=_text(data, "camera"),
            location=_triple(data.get("location"), "location"),
            rotation=_triple(data.get("rotation"), "rotation"),
            resolution=_resolution(data.get("resolution")),
            quality=_quality(data.get("quality", {})),
            git_commit=commit,
            captured_at=_text(data, "captured_at"),
            provenance=_provenance(data.get("provenance", [])),
        )


def sidecar_path_for(image: str | Path) -> Path:
    """Return the sidecar path next to an image path."""
    return Path(image).with_suffix(".json")


def write_sidecar(path: str | Path, sidecar: Sidecar) -> None:
    """Write ``sidecar`` as sorted, indented JSON."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sidecar.to_dict(), indent=2, sort_keys=True) + "\n", "utf-8")


def _read_json(path: Path, error_code: str, what: str) -> Any:
    try:
        if path.stat().st_size > MAX_SIDECAR_BYTES:
            raise CaptureError(error_code, f"{what} is too large")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CaptureError(error_code, f"{what} cannot be read as JSON") from exc


def load_sidecar(path: str | Path) -> Sidecar:
    """Load and validate a sidecar file.

    Raises:
        CaptureError: ``unknown_capture`` when missing, ``invalid_sidecar`` when malformed.
    """
    target = Path(path)
    if not target.is_file():
        raise CaptureError("unknown_capture", f"no sidecar at {target.name[:80]!r}")
    return Sidecar.from_dict(_read_json(target, "invalid_sidecar", "sidecar"))


def read_provenance(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Read an optional ``provenance.json``; returns ``()`` when absent.

    Accepts a JSON list, or an object with an ``entries`` or ``provenance`` list. Only the last
    ``MAX_PROVENANCE`` entries are kept.

    Raises:
        CaptureError: ``invalid_sidecar`` when the file exists but is malformed.
    """
    target = Path(path)
    if not target.is_file():
        return ()
    data = _read_json(target, "invalid_sidecar", "provenance.json")
    if isinstance(data, dict):
        data = data.get("entries", data.get("provenance"))
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise _bad("provenance.json must hold a list of objects")
    return tuple(data[-MAX_PROVENANCE:])
