"""Pure core of the capture toolset. Never imports ``unreal``."""

from __future__ import annotations

from .errors import CaptureError
from .gitinfo import read_git_commit
from .logscan import recent_errors
from .markdown import build_bug_markdown, build_contact_sheet_md
from .paths import capture_path
from .resolution import parse_resolution
from .sidecar import Sidecar

__all__ = [
    "CaptureError",
    "Sidecar",
    "build_bug_markdown",
    "build_contact_sheet_md",
    "capture_path",
    "parse_resolution",
    "read_git_commit",
    "recent_errors",
]
