"""Resolve Unreal APIs that moved between engine versions.

UE 5.x deprecates ``EditorLevelLibrary`` in favor of editor subsystems. These helpers prefer the
subsystem and fall back to the legacy library, so the adapter works on UE 5.8 and on older 5.x
builds. Which one the editor actually exposes is confirmed by ``tests/ue_smoke.py`` in Unreal.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from typing import Any

__all__ = [
    "actor_api",
    "editor_api",
    "level_api",
    "set_viewport_camera",
    "transaction",
]


def _subsystem(ue: Any, name: str) -> Any:
    subsystem_cls = getattr(ue, name, None)
    getter = getattr(ue, "get_editor_subsystem", None)
    if subsystem_cls is None or getter is None:
        return None
    return getter(subsystem_cls)


def editor_api(ue: Any) -> Any:
    """Return ``UnrealEditorSubsystem`` (world, viewport camera) or ``EditorLevelLibrary``."""
    return _subsystem(ue, "UnrealEditorSubsystem") or ue.EditorLevelLibrary


def actor_api(ue: Any) -> Any:
    """Return ``EditorActorSubsystem`` (list and spawn actors) or ``EditorLevelLibrary``."""
    return _subsystem(ue, "EditorActorSubsystem") or ue.EditorLevelLibrary


def level_api(ue: Any) -> Any:
    """Return ``LevelEditorSubsystem`` (pilot an actor) or ``EditorLevelLibrary``."""
    return _subsystem(ue, "LevelEditorSubsystem") or ue.EditorLevelLibrary


def set_viewport_camera(ue: Any, location: Any, rotation: Any) -> bool:
    """Move the level viewport camera when ``set_level_viewport_camera_info`` exists.

    Returns False (and changes nothing) when the editor does not expose it; the caller then falls
    back to spawning and piloting a camera actor.
    """
    subsystem = _subsystem(ue, "UnrealEditorSubsystem")
    setter = getattr(subsystem, "set_level_viewport_camera_info", None)
    if setter is None:
        return False
    setter(location, rotation)
    return True


def transaction(ue: Any, description: str) -> AbstractContextManager[Any]:
    """Return ``ScopedEditorTransaction`` (undoable with Ctrl+Z) or a no-op context."""
    scoped = getattr(ue, "ScopedEditorTransaction", None)
    if scoped is None:
        return nullcontext()
    context: AbstractContextManager[Any] = scoped(description)
    return context
