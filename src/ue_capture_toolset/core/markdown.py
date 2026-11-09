"""Markdown renderers for bug evidence and contact sheets. They never read image files."""

from __future__ import annotations

import json
from collections.abc import Sequence
from urllib.parse import quote

from .errors import CaptureError
from .sidecar import Sidecar

__all__ = [
    "MAX_ERRORS",
    "MAX_NOTES",
    "MAX_SHEET",
    "SEVERITIES",
    "build_bug_markdown",
    "build_contact_sheet_md",
    "normalize_severity",
]

SEVERITIES = ("low", "medium", "high", "critical")
MAX_ERRORS = 20
MAX_NOTES = 20_000
MAX_SHEET = 200


def _inline(text: object, limit: int = 200) -> str:
    return " ".join(str(text).split())[:limit].replace("`", "'")


def _link(path: str) -> str:
    return quote(_inline(path, 300), safe="/")


def _alt(text: str) -> str:
    return _inline(text, 120).replace("[", "(").replace("]", ")")


def _triple(values: tuple[float, float, float]) -> str:
    return f"({values[0]:.2f}, {values[1]:.2f}, {values[2]:.2f})"


def normalize_severity(value: str) -> str:
    """Return the lower-case severity or raise ``CaptureError`` ``invalid_severity``."""
    severity = str(value).strip().lower()
    if severity not in SEVERITIES:
        raise CaptureError("invalid_severity", f"severity must be one of {', '.join(SEVERITIES)}")
    return severity


def build_bug_markdown(
    sidecar: Sidecar,
    *,
    severity: str,
    title: str,
    notes: str = "",
    errors: Sequence[str] = (),
    image_link: str | None = None,
    mode: str | None = None,
    player: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None,
) -> str:
    """Render a bug report from a capture sidecar, recent log errors and free notes.

    ``mode`` (``editor`` or ``pie``) and ``player`` (location, rotation of the player pawn) add
    context lines when given.

    Raises:
        CaptureError: ``invalid_severity`` or ``input_too_large`` (notes).
    """
    level = normalize_severity(severity)
    if len(notes) > MAX_NOTES:
        raise CaptureError("input_too_large", f"notes must be at most {MAX_NOTES} characters")
    link = _link(image_link if image_link is not None else sidecar.image)
    commit = sidecar.git_commit or "unknown"
    width, height = sidecar.resolution
    lines = [
        f"# Bug: {_inline(title, 120)}",
        "",
        f"- **Severity:** {level}",
        f"- **Map:** {_inline(sidecar.map)}",
        f"- **Camera:** {_inline(sidecar.camera)}",
        f"- **Location:** {_triple(sidecar.location)}",
        f"- **Rotation:** {_triple(sidecar.rotation)}",
        *([f"- **Mode:** {_inline(mode, 20)}"] if mode else []),
        *(
            [
                f"- **Player location:** {_triple(player[0])}",
                f"- **Player rotation:** {_triple(player[1])}",
            ]
            if player
            else []
        ),
        f"- **Resolution:** {width}x{height}",
        f"- **Commit:** {_inline(commit, 64)}",
        f"- **Captured at:** {_inline(sidecar.captured_at)}",
        "",
        f"![{_alt(title)}]({link})",
        "",
        "## Quality preset",
        "",
    ]
    if sidecar.quality:
        for key, value in sorted(sidecar.quality.items()):
            lines.append(f"- `{_inline(key, 100)}`: {value}")
    else:
        lines.append("- none recorded")
    lines += ["", "## Recent errors", ""]
    shown = list(errors)[-MAX_ERRORS:]
    if shown:
        lines += [f"- `{_inline(entry, 500)}`" for entry in shown]
    else:
        lines.append("- none recorded")
    if sidecar.provenance:
        lines += ["", "## Provenance", ""]
        for entry in sidecar.provenance:
            lines.append(f"- {_inline(json.dumps(entry, sort_keys=True, default=str), 300)}")
    if notes.strip():
        lines += ["", "## Notes", ""]
        lines += [f"> {line.rstrip()}".rstrip() for line in notes.strip().splitlines()]
    return "\n".join(lines) + "\n"


def build_contact_sheet_md(sidecars: Sequence[Sidecar], *, title: str = "Contact sheet") -> str:
    """Render a contact sheet linking every capture image (images are never opened).

    Raises:
        CaptureError: ``too_many_captures`` above ``MAX_SHEET`` sidecars.
    """
    if len(sidecars) > MAX_SHEET:
        raise CaptureError(
            "too_many_captures", f"a contact sheet holds at most {MAX_SHEET} captures"
        )
    count = len(sidecars)
    lines = [f"# {_inline(title, 120)}", "", f"{count} capture{'s' if count != 1 else ''}."]
    for index, sidecar in enumerate(sidecars, start=1):
        commit = sidecar.git_commit[:7] if sidecar.git_commit else "unknown"
        lines += [
            "",
            f"## {index}. {_inline(sidecar.label, 80)}",
            "",
            f"![{_alt(sidecar.label)}]({_link(sidecar.image)})",
            "",
            f"- Map: {_inline(sidecar.map)}",
            f"- Camera: {_inline(sidecar.camera)}",
            f"- Captured at: {_inline(sidecar.captured_at)}",
            f"- Commit: {_inline(commit, 64)}",
        ]
    return "\n".join(lines) + "\n"
