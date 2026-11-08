"""Pure core and Unreal adapter for reproducible captures with JSON sidecars."""

from __future__ import annotations

from .adapter import (
    BugResult,
    Capture,
    ListResult,
    PairResult,
    SeriesResult,
    capture_bug,
    capture_pair,
    capture_series,
    capture_viewport,
    list_captures,
    poll_capture,
)
from .core import (
    CaptureError,
    Sidecar,
    build_bug_markdown,
    build_contact_sheet_md,
    capture_path,
    parse_resolution,
    read_git_commit,
    recent_errors,
)

__all__ = [
    "BugResult",
    "Capture",
    "CaptureError",
    "ListResult",
    "PairResult",
    "SeriesResult",
    "Sidecar",
    "__version__",
    "build_bug_markdown",
    "build_contact_sheet_md",
    "capture_bug",
    "capture_pair",
    "capture_path",
    "capture_series",
    "capture_viewport",
    "list_captures",
    "parse_resolution",
    "poll_capture",
    "read_git_commit",
    "recent_errors",
]

__version__ = "0.1.0"
