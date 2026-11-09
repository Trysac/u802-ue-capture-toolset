"""MCP-facing functions: flat, JSON-friendly parameters in, one JSON string out.

The Unreal plugin's toolset class (``plugin/CaptureToolset/Content/Python``) only forwards to these
functions with the real ``unreal`` module, so everything an agent sees is tested here with a fake.
Inputs are primitives (lists travel as JSON strings) and every result is a JSON object whose first
key is ``summary``. Errors never raise to the agent: they come back as
``{"summary": "error: ...", "error": {"code": ..., "message": ...}}``.

The project's Saved folder comes from ``unreal.Paths.project_saved_dir()``; the agent never passes
it. ``HighResShot`` is asynchronous: capture tools return at once with a ``capture_id`` (the image
path relative to Saved) and ``capture_status`` checks, without waiting, whether the file exists.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import adapter
from .adapter import Capture
from .core.errors import CaptureError
from .core.markdown import MAX_SHEET
from .core.markdown import build_contact_sheet_md as _render_contact_sheet
from .core.sidecar import Sidecar, load_sidecar, sidecar_path_for

MAX_JSON_CHARS = 1_000_000
MAX_REF_CHARS = 1000
MAX_TIMEOUT_S = 600.0


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _plain(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def to_json(result: Any) -> str:
    """Serialize a result with ``summary`` first."""
    data = _plain(result)
    if isinstance(data, dict) and "summary" in data:
        data = {"summary": data["summary"], **{k: v for k, v in data.items() if k != "summary"}}
    return json.dumps(data, ensure_ascii=False)


def _error(code: str, message: str) -> str:
    return json.dumps(
        {"summary": f"error: {message[:200]}", "error": {"code": code, "message": message[:200]}}
    )


def _run(call: Callable[[], Any]) -> str:
    try:
        return to_json(call())
    except CaptureError as exc:
        return _error(exc.code, exc.message)
    except OSError as exc:
        return _error("io_error", f"{type(exc).__name__}: {exc}")
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return _error("unreal_error", f"{type(exc).__name__}: {exc}")


def _parse_json(raw: str, what: str) -> Any:
    if not isinstance(raw, str) or len(raw) > MAX_JSON_CHARS:
        raise CaptureError("invalid_json", f"{what} must be a JSON string under 1 MB")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CaptureError("invalid_json", f"{what} is not valid JSON: {exc.msg}") from exc


def _string_list(raw: str, what: str, limit: int) -> list[str]:
    data = _parse_json(raw, what)
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise CaptureError("invalid_json", f"{what} must be a JSON list of strings")
    if not 1 <= len(data) <= limit:
        raise CaptureError("invalid_json", f"{what} must hold between 1 and {limit} entries")
    return data


def _saved(ue: Any) -> Path:
    raw = str(ue.Paths.project_saved_dir())
    convert = getattr(ue.Paths, "convert_relative_path_to_full", None)
    return Path(str(convert(raw)) if convert is not None else raw).resolve()


def _capture_id(saved: Path, image: str | Path) -> str:
    return Path(image).resolve().relative_to(saved).as_posix()


def _image_for(saved: Path, ref: str) -> Path:
    if not isinstance(ref, str) or not ref.strip() or len(ref) > MAX_REF_CHARS:
        raise CaptureError("unknown_capture", "give a capture id or path")
    candidate = Path(ref.strip())
    if not candidate.is_absolute():
        candidate = saved / candidate
    resolved = candidate.resolve()
    inside = resolved.is_relative_to((saved / "Captures").resolve())
    if not inside or resolved.suffix.lower() not in (".png", ".json", ".md"):
        raise CaptureError("unknown_capture", "capture must be a file under Saved/Captures")
    return resolved.with_suffix(".png")


def _capture_row(saved: Path, capture: Capture) -> dict[str, Any]:
    width, height = capture.resolution
    return {
        "summary": capture.summary,
        "capture_id": _capture_id(saved, capture.image_path),
        "status": capture.status,
        "camera": capture.camera,
        "resolution": f"{width}x{height}",
        "image_path": capture.image_path,
        "sidecar_path": capture.sidecar_path,
    }


def _sidecar_row(sidecar: Sidecar) -> dict[str, Any]:
    width, height = sidecar.resolution
    return {
        "capture_id": sidecar.image,
        "label": sidecar.label,
        "map": sidecar.map,
        "camera": sidecar.camera,
        "captured_at": sidecar.captured_at,
        "resolution": f"{width}x{height}",
        "git_commit": sidecar.git_commit,
    }


def _poll_one(saved: Path, ref: str, timeout_s: float) -> dict[str, Any]:
    image = _image_for(saved, ref)
    sidecar_file = sidecar_path_for(image)
    sidecar = load_sidecar(sidecar_file)
    pending = Capture(
        image_path=str(image),
        sidecar_path=str(sidecar_file),
        label=sidecar.label,
        camera=sidecar.camera,
        resolution=sidecar.resolution,
        requested_at=sidecar_file.stat().st_mtime,
        timeout_s=timeout_s,
        status="pending",
        summary="",
    )
    try:
        status = adapter.poll_capture(pending, clock=time.time).status
    except CaptureError:  # poll_capture raises only capture_timeout
        status = "timeout"
    return {"capture_id": _capture_id(saved, image), "status": status, "image_path": str(image)}


def capture_viewport(
    ue: Any, label: str = "viewport", resolution: str = "1920x1080", camera: str = ""
) -> str:
    """Request a HighResShot of the level viewport (or of a camera actor); returns at once."""

    def call() -> Any:
        saved = _saved(ue)
        shot = adapter.capture_viewport(ue, saved, label, resolution, camera=camera or None)
        return _capture_row(saved, shot)

    return _run(call)


def capture_status(ue: Any, capture: str, timeout_s: float = adapter.DEFAULT_TIMEOUT_S) -> str:
    """Check once (no waiting) whether one capture, or a JSON list of captures, is on disk."""

    def call() -> Any:
        if not 0 < timeout_s <= MAX_TIMEOUT_S:
            raise CaptureError("invalid_timeout", f"timeout_s must be in (0, {MAX_TIMEOUT_S:g}]")
        saved = _saved(ue)
        stripped = capture.strip() if isinstance(capture, str) else capture
        refs = (
            _string_list(stripped, "capture", MAX_SHEET)
            if isinstance(stripped, str) and stripped.startswith("[")
            else [stripped]
        )
        rows = [_poll_one(saved, ref, timeout_s) for ref in refs]
        counts = {s: sum(r["status"] == s for r in rows) for s in ("ready", "pending", "timeout")}
        summary = f"{counts['ready']} of {len(rows)} ready"
        if counts["pending"]:
            summary += f", {counts['pending']} pending (call again)"
        if counts["timeout"]:
            summary += f", {counts['timeout']} timed out"
        return {"summary": summary, "done": counts["pending"] == 0, **counts, "captures": rows}

    return _run(call)


def capture_pair(ue: Any, before: str, label: str = "after", resolution: str = "") -> str:
    """Request an "after" capture from the exact transform of an earlier capture."""

    def call() -> Any:
        saved = _saved(ue)
        result = adapter.capture_pair(ue, saved, before, label, resolution or None)
        row = _capture_row(saved, result.after)
        row["summary"] = result.summary
        row["before_id"] = result.before.image
        return row

    return _run(call)


def capture_series(
    ue: Any,
    label: str,
    cameras_json: str = "",
    tag: str = "",
    resolution: str = "1920x1080",
    cursor: int = 0,
) -> str:
    """Request the capture of camera number ``cursor`` of a series; returns the next cursor."""

    def call() -> Any:
        if bool(cameras_json) == bool(tag):
            raise CaptureError("invalid_series", "give either cameras_json or tag")
        cameras = (
            _string_list(cameras_json, "cameras_json", adapter.MAX_SERIES)
            if cameras_json
            else list(adapter.cameras_with_tag(ue, tag))
        )
        saved = _saved(ue)
        result = adapter.capture_series(
            ue, saved, label, cameras, resolution, cursor=cursor, limit=1
        )
        return {
            "summary": result.summary,
            "cameras": cameras,
            "captures": [_capture_row(saved, c) for c in result.captures],
            "cursor": result.cursor,
        }

    return _run(call)


def capture_bug(
    ue: Any,
    title: str,
    severity: str = "medium",
    notes: str = "",
    label: str = "bug",
    resolution: str = "1920x1080",
) -> str:
    """Capture the viewport and write a Markdown bug report next to the image."""

    def call() -> Any:
        saved = _saved(ue)
        result = adapter.capture_bug(
            ue, saved, title, severity, label=label, resolution=resolution, notes=notes
        )
        row = _capture_row(saved, result.capture)
        row["summary"] = result.summary
        row["report_path"] = result.report_path
        row["error_count"] = result.error_count
        row["markdown"] = Path(result.report_path).read_text(encoding="utf-8")
        return row

    return _run(call)


def _since(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise CaptureError("invalid_filter", "since must be an ISO date or date-time") from exc


def _after(sidecar: Sidecar, since: datetime | None) -> bool:
    if since is None:
        return True
    try:
        return datetime.fromisoformat(sidecar.captured_at) >= since
    except (TypeError, ValueError):
        return False


def list_captures(ue: Any, limit: int = 100, since: str = "", label: str = "") -> str:
    """List the newest captures (oldest first), optionally since a date or matching a label."""

    def call() -> Any:
        start = _since(since)
        needle = label.strip().lower()
        listed = adapter.list_captures(ue, _saved(ue), adapter.MAX_LIST)
        found = [
            s
            for s in listed.captures
            if _after(s, start) and (not needle or needle in s.label.lower())
        ]
        shown = found[-max(1, min(limit, adapter.MAX_LIST)) :]
        return {
            "summary": f"{len(shown)} of {len(found)} matching captures, {listed.skipped} skipped",
            "captures": [_sidecar_row(s) for s in shown],
            "skipped": listed.skipped,
        }

    return _run(call)


def build_contact_sheet_md(ue: Any, captures_json: str, title: str = "Contact sheet") -> str:
    """Render a Markdown contact sheet for a JSON list of capture ids or paths."""

    def call() -> Any:
        saved = _saved(ue)
        refs = _string_list(captures_json, "captures_json", MAX_SHEET)
        sidecars = [load_sidecar(sidecar_path_for(_image_for(saved, ref))) for ref in refs]
        content = _render_contact_sheet(sidecars, title=title)
        return {
            "summary": f"contact sheet with {len(sidecars)} captures ({len(content)} chars)",
            "content": content,
            "count": len(sidecars),
        }

    return _run(call)
