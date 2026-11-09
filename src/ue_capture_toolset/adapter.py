"""Thin adapter between the pure core and the Unreal Python API.

Every function takes ``ue`` first: the ``unreal`` module or a fake. ``unreal`` is never imported
here. ``HighResShot`` is asynchronous, so capture functions return a pending ``Capture`` and
``poll_capture`` checks for the file against a deadline; nothing sleeps on the game thread.
Engine APIs that moved between UE 5.x versions are resolved through ``compat``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from . import compat
from .core.errors import CaptureError
from .core.gitinfo import read_git_commit
from .core.logscan import read_log_tail, recent_errors
from .core.markdown import build_bug_markdown, normalize_severity
from .core.paths import capture_path, slugify
from .core.resolution import parse_resolution
from .core.sidecar import Sidecar, load_sidecar, read_provenance, sidecar_path_for, write_sidecar

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "MAX_LIST",
    "MAX_SERIES",
    "QUALITY_GROUPS",
    "BugResult",
    "Capture",
    "ListResult",
    "PairResult",
    "SeriesResult",
    "cameras_with_tag",
    "capture_bug",
    "capture_pair",
    "capture_series",
    "capture_viewport",
    "list_captures",
    "poll_capture",
]

DEFAULT_TIMEOUT_S = 30.0
MAX_SERIES = 50
MAX_LIST = 500
QUALITY_GROUPS = (
    "ViewDistanceQuality",
    "AntiAliasingQuality",
    "ShadowQuality",
    "GlobalIlluminationQuality",
    "ReflectionQuality",
    "PostProcessQuality",
    "TextureQuality",
    "EffectsQuality",
    "FoliageQuality",
    "ShadingQuality",
)


@dataclass(frozen=True)
class Capture:
    """A requested capture. ``status`` is ``pending`` or ``ready``."""

    image_path: str
    sidecar_path: str
    label: str
    camera: str
    resolution: tuple[int, int]
    requested_at: float
    timeout_s: float
    status: str
    summary: str


@dataclass(frozen=True)
class PairResult:
    """Result of ``capture_pair``: the before sidecar and the pending after capture."""

    before: Sidecar
    after: Capture
    camera: str
    summary: str


@dataclass(frozen=True)
class SeriesResult:
    """Result of ``capture_series``. ``cursor`` is the next camera index, None when done."""

    captures: tuple[Capture, ...]
    summary: str
    cursor: int | None = None


@dataclass(frozen=True)
class BugResult:
    """Result of ``capture_bug``."""

    capture: Capture
    report_path: str
    error_count: int
    summary: str


@dataclass(frozen=True)
class ListResult:
    """Result of ``list_captures``, oldest first."""

    captures: tuple[Sidecar, ...]
    skipped: int
    summary: str


@dataclass(frozen=True)
class _Pose:
    camera: str
    location: tuple[float, float, float]
    rotation: tuple[float, float, float]


def _vec(value: Any) -> tuple[float, float, float]:
    return (float(value.x), float(value.y), float(value.z))


def _rot(value: Any) -> tuple[float, float, float]:
    return (float(value.pitch), float(value.yaw), float(value.roll))


def _world(ue: Any) -> Any:
    return compat.editor_api(ue).get_editor_world()


def _quality(ue: Any) -> dict[str, int]:
    library = ue.SystemLibrary
    return {
        f"sg.{group}": int(library.get_console_variable_int_value(f"sg.{group}"))
        for group in QUALITY_GROUPS
    }


def _viewport_pose(ue: Any) -> _Pose:
    info = compat.editor_api(ue).get_level_viewport_camera_info()
    location, rotation = tuple(info)[-2:]
    return _Pose("viewport", _vec(location), _rot(rotation))


def _actor_pose(name: str, actor: Any) -> _Pose:
    return _Pose(name, _vec(actor.get_actor_location()), _rot(actor.get_actor_rotation()))


def _find_camera(ue: Any, name: str) -> Any:
    for actor in compat.actor_api(ue).get_all_level_actors():
        if actor.get_actor_label() == name:
            return actor
    raise CaptureError("camera_not_found", f"no actor labelled {name[:80]!r}")


def cameras_with_tag(ue: Any, tag: str) -> tuple[str, ...]:
    """Return the sorted labels of level actors that carry the actor tag ``tag`` (read-only).

    Raises:
        CaptureError: ``camera_not_found`` when no actor has the tag.
    """
    if not isinstance(tag, str) or not tag.strip() or len(tag) > 200:
        raise CaptureError("invalid_series", "tag must be non-empty text")
    labels = sorted(
        str(actor.get_actor_label())
        for actor in compat.actor_api(ue).get_all_level_actors()
        if actor.actor_has_tag(tag)
    )
    if not labels:
        raise CaptureError("camera_not_found", f"no actor tagged {tag[:80]!r}")
    return tuple(labels)


def _request_shot(
    ue: Any,
    saved_dir: str | Path,
    label: str,
    resolution: str,
    pose: _Pose,
    at: datetime | None,
    clock: Callable[[], float],
    timeout_s: float,
) -> tuple[Capture, Sidecar]:
    width, height = parse_resolution(resolution)
    saved = Path(saved_dir)
    when = at if at is not None else datetime.now()
    image = capture_path(saved, label, when)
    target = image.resolve().as_posix()
    if '"' in target:
        raise CaptureError("invalid_path", "saved_dir must not contain double quotes")
    sidecar = Sidecar(
        image=image.relative_to(saved).as_posix(),
        label=label,
        map=str(_world(ue).get_path_name()),
        camera=pose.camera,
        location=pose.location,
        rotation=pose.rotation,
        resolution=(width, height),
        quality=_quality(ue),
        git_commit=read_git_commit(saved.parent),
        captured_at=when.isoformat(timespec="seconds"),
        provenance=read_provenance(saved / "provenance.json"),
    )
    sidecar_file = sidecar_path_for(image)
    write_sidecar(sidecar_file, sidecar)
    ue.SystemLibrary.execute_console_command(
        _world(ue), f'HighResShot {width}x{height} filename="{target}"'
    )
    capture = Capture(
        image_path=str(image),
        sidecar_path=str(sidecar_file),
        label=label,
        camera=pose.camera,
        resolution=(width, height),
        requested_at=clock(),
        timeout_s=timeout_s,
        status="pending",
        summary=f"Requested {width}x{height} capture of {pose.camera}: pending {image.name}",
    )
    return capture, sidecar


def poll_capture(capture: Capture, *, clock: Callable[[], float] = time.monotonic) -> Capture:
    """Check once whether the image exists. Returns the capture, ``ready`` or still ``pending``.

    Raises:
        CaptureError: ``capture_timeout`` once ``timeout_s`` has passed without the file.
    """
    image = Path(capture.image_path)
    if image.is_file() and image.stat().st_size > 0:
        return replace(capture, status="ready", summary=f"Capture ready: {image.name}")
    if clock() - capture.requested_at > capture.timeout_s:
        raise CaptureError("capture_timeout", f"{image.name[:80]} did not appear in time")
    return capture


def capture_viewport(
    ue: Any,
    saved_dir: str | Path,
    label: str = "viewport",
    resolution: str = "1920x1080",
    *,
    camera: str | None = None,
    at: datetime | None = None,
    clock: Callable[[], float] = time.monotonic,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Capture:
    """Request a screenshot of the editor viewport and write its sidecar.

    With ``camera`` (an actor label) the viewport first pilots that actor.
    """
    if camera:
        parse_resolution(resolution)
        actor = _find_camera(ue, camera)
        compat.level_api(ue).pilot_level_actor(actor)
        pose = _actor_pose(camera, actor)
    else:
        pose = _viewport_pose(ue)
    capture, _ = _request_shot(ue, saved_dir, label, resolution, pose, at, clock, timeout_s)
    return capture


def _load_before(saved: Path, before: str | Path) -> Sidecar:
    candidate = Path(before)
    if not candidate.is_absolute():
        candidate = saved / candidate
    resolved = candidate.resolve()
    if not resolved.is_relative_to(saved.resolve()) or resolved.suffix.lower() not in (
        ".png",
        ".json",
    ):
        raise CaptureError("unknown_capture", "before must be a capture inside the Saved folder")
    return load_sidecar(sidecar_path_for(resolved))


def capture_pair(
    ue: Any,
    saved_dir: str | Path,
    before: str | Path,
    label: str = "after",
    resolution: str | None = None,
    *,
    at: datetime | None = None,
    clock: Callable[[], float] = time.monotonic,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> PairResult:
    """Request an \"after\" capture from the transform recorded for ``before``.

    ``before`` is a sidecar or image path (absolute, or relative to ``saved_dir``). When the editor
    exposes ``UnrealEditorSubsystem.set_level_viewport_camera_info`` the viewport camera is moved
    there; otherwise a camera actor is spawned (inside an undoable transaction) and piloted. The
    spawned actor stays in the level; nothing is deleted.
    """
    saved = Path(saved_dir)
    prior = _load_before(saved, before)
    size = resolution if resolution is not None else f"{prior.resolution[0]}x{prior.resolution[1]}"
    parse_resolution(size)
    x, y, z = prior.location
    pitch, yaw, roll = prior.rotation
    location = ue.Vector(x=x, y=y, z=z)
    rotation = ue.Rotator(roll=roll, pitch=pitch, yaw=yaw)
    if compat.set_viewport_camera(ue, location, rotation):
        name = "viewport"
        pose = _Pose(name, prior.location, prior.rotation)
    else:
        name = f"Pair_{slugify(label)}"
        with compat.transaction(ue, f"Capture pair camera {name}"):
            actor = compat.actor_api(ue).spawn_actor_from_class(ue.CameraActor, location, rotation)
            actor.set_actor_label(name)
        compat.level_api(ue).pilot_level_actor(actor)
        pose = _actor_pose(name, actor)
    capture, _ = _request_shot(ue, saved, label, size, pose, at, clock, timeout_s)
    return PairResult(
        before=prior,
        after=capture,
        camera=name,
        summary=f"Pair: before {prior.image}, after {Path(capture.image_path).name} (pending)",
    )


def capture_series(
    ue: Any,
    saved_dir: str | Path,
    label: str,
    cameras: Sequence[str],
    resolution: str = "1920x1080",
    *,
    cursor: int = 0,
    limit: int = MAX_SERIES,
    at: datetime | None = None,
    clock: Callable[[], float] = time.monotonic,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> SeriesResult:
    """Request one capture per named camera actor, ``limit`` cameras from ``cursor`` on.

    All cameras are checked before any shot. The returned ``cursor`` is the next index to request
    (None when the series is complete); wait for the pending captures before continuing.
    """
    if isinstance(cameras, str) or not 1 <= len(cameras) <= MAX_SERIES:
        raise CaptureError("invalid_series", f"give between 1 and {MAX_SERIES} camera names")
    if not 0 <= cursor < len(cameras) or limit < 1:
        raise CaptureError("invalid_series", "cursor must index a camera and limit be positive")
    parse_resolution(resolution)
    actors = [(name, _find_camera(ue, name)) for name in cameras]
    end = min(cursor + limit, len(actors))
    captures: list[Capture] = []
    for name, actor in actors[cursor:end]:
        compat.level_api(ue).pilot_level_actor(actor)
        pose = _actor_pose(name, actor)
        shot_label = f"{label}-{name}"
        capture, _ = _request_shot(
            ue, saved_dir, shot_label, resolution, pose, at, clock, timeout_s
        )
        captures.append(capture)
    remaining = len(actors) - end
    return SeriesResult(
        captures=tuple(captures),
        summary=f"Requested {len(captures)} captures for series {label[:60]!r}"
        + (f", {remaining} cameras left" if remaining else ""),
        cursor=end if remaining else None,
    )


def _pick_log(saved: Path, log_path: str | Path | None) -> Path | None:
    if log_path is not None:
        candidate = Path(log_path)
        if not candidate.is_absolute():
            candidate = saved / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(saved.resolve()):
            raise CaptureError("invalid_path", "log_path must be inside the Saved folder")
        return resolved
    logs = sorted((saved / "Logs").glob("*.log"), key=lambda p: (p.stat().st_mtime, p.name))
    return logs[-1] if logs else None


def capture_bug(
    ue: Any,
    saved_dir: str | Path,
    title: str,
    severity: str = "medium",
    *,
    label: str = "bug",
    resolution: str = "1920x1080",
    notes: str = "",
    log_path: str | Path | None = None,
    at: datetime | None = None,
    clock: Callable[[], float] = time.monotonic,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> BugResult:
    """Capture the viewport and write a Markdown bug report next to the image.

    Recent errors come from ``log_path`` or the newest ``Logs/*.log`` under ``saved_dir``.
    """
    level = normalize_severity(severity)
    saved = Path(saved_dir)
    log = _pick_log(saved, log_path)
    pose = _viewport_pose(ue)
    capture, sidecar = _request_shot(ue, saved, label, resolution, pose, at, clock, timeout_s)
    errors = recent_errors(read_log_tail(log)) if log is not None else []
    markdown = build_bug_markdown(
        sidecar,
        severity=level,
        title=title,
        notes=notes,
        errors=errors,
        image_link=Path(capture.image_path).name,
    )
    report = Path(capture.image_path).with_suffix(".md")
    report.write_text(markdown, encoding="utf-8")
    return BugResult(
        capture=capture,
        report_path=str(report),
        error_count=len(errors),
        summary=f"Bug report ({level}) with {len(errors)} recent errors: {report.name}",
    )


def list_captures(ue: Any, saved_dir: str | Path, limit: int = 100) -> ListResult:
    """List the newest ``limit`` capture sidecars (1 to ``MAX_LIST``), oldest first.

    ``ue`` is accepted for a uniform signature; listing only reads files. Unreadable sidecars
    are counted in ``skipped``.
    """
    count = max(1, min(limit, MAX_LIST))
    files = sorted((Path(saved_dir) / "Captures").glob("*/*.json"))[-count:]
    found: list[Sidecar] = []
    skipped = 0
    for file in files:
        try:
            found.append(load_sidecar(file))
        except CaptureError:
            skipped += 1
    return ListResult(
        captures=tuple(found),
        skipped=skipped,
        summary=f"{len(found)} captures listed, {skipped} skipped",
    )
