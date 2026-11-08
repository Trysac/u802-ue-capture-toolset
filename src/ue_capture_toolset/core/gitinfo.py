"""Read the current git commit straight from ``.git`` files; never runs git."""

from __future__ import annotations

import re
from pathlib import Path

__all__ = ["MAX_PACKED_BYTES", "MAX_REF_BYTES", "read_git_commit"]

MAX_REF_BYTES = 65_536
MAX_PACKED_BYTES = 16_000_000
_SHA = re.compile(r"[0-9a-f]{40}")
_SAFE_REF = re.compile(r"refs/[A-Za-z0-9._+@/-]+")


def _read_small(path: Path, limit: int) -> str | None:
    try:
        with open(path, "rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        return None
    if len(data) > limit:
        return None
    return data.decode("utf-8", "replace").strip()


def _git_dir(project: Path) -> Path | None:
    dot_git = project / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        text = _read_small(dot_git, MAX_REF_BYTES)
        if text and text.startswith("gitdir:"):
            target = Path(text[len("gitdir:") :].strip())
            if not target.is_absolute():
                target = dot_git.parent / target
            if target.is_dir():
                return target
    return None


def _ref_dirs(git_dir: Path) -> list[Path]:
    dirs = [git_dir]
    text = _read_small(git_dir / "commondir", MAX_REF_BYTES)
    if text:
        common = (git_dir / text).resolve()
        if common.is_dir() and common != git_dir.resolve():
            dirs.append(common)
    return dirs


def _resolve_ref(ref: str, dirs: list[Path]) -> str | None:
    for directory in dirs:
        loose = _read_small(directory / ref, MAX_REF_BYTES)
        if loose and _SHA.fullmatch(loose.lower()):
            return loose.lower()
    for directory in dirs:
        packed = _read_small(directory / "packed-refs", MAX_PACKED_BYTES)
        if not packed:
            continue
        for line in packed.splitlines():
            if not line or line[0] in "#^":
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2 and parts[1].strip() == ref and _SHA.fullmatch(parts[0]):
                return parts[0]
    return None


def read_git_commit(project_dir: str | Path) -> str | None:
    """Return the 40-character commit sha of HEAD for ``project_dir``, or ``None``.

    Handles branches (loose refs and ``packed-refs``), detached HEAD and worktrees. Only the given
    folder is inspected, not its parents. Any unreadable or unexpected content gives ``None``.
    """
    git_dir = _git_dir(Path(project_dir))
    if git_dir is None:
        return None
    head = _read_small(git_dir / "HEAD", MAX_REF_BYTES)
    if not head:
        return None
    if head.startswith("ref:"):
        ref = head[4:].strip()
        if not _SAFE_REF.fullmatch(ref) or ".." in ref or ref.endswith("/"):
            return None
        return _resolve_ref(ref, _ref_dirs(git_dir))
    if _SHA.fullmatch(head.lower()):
        return head.lower()
    return None
