# ue-capture-toolset

[![PyPI version](https://img.shields.io/pypi/v/trysac-ue-capture-toolset)](https://pypi.org/project/trysac-ue-capture-toolset/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-ue-capture-toolset)](LICENSE)
[![CI](https://github.com/Trysac/u802-ue-capture-toolset/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u802-ue-capture-toolset/actions/workflows/ci.yml)

Pure core and Unreal adapter for reproducible captures with JSON sidecars, bug evidence and Markdown contact sheets.

## Problem

Agents building games in Unreal Engine 5.8 need reproducible screenshots for dev logs, bug reports and before/after comparisons. Captures are often ad hoc files with no record of camera, map, quality preset or commit. This library writes a JSON sidecar next to every capture that records that context.

## Install in Unreal Engine (the MCP toolset)

1. Build the plugin: `uv run python tools/build_plugin.py` (or download the zip from a release). It
   creates `dist/CaptureToolset-<version>.zip`.
2. Unzip it into `<YourProject>/Plugins/` (you get `Plugins/CaptureToolset/`).
3. In the editor enable **Unreal MCP**, **All Toolsets** and **Capture Toolset**, restart, and
   turn on *Editor Preferences > General > Model Context Protocol > Auto Start Server*.
4. Run `ModelContextProtocol.GenerateClientConfig ClaudeCode` in the console (writes `.mcp.json`),
   then start your agent from the project root. If the editor was already running, run
   `ModelContextProtocol.RefreshTools`.
5. The agent finds the toolset `CaptureTools` through `list_toolsets` and calls it with
   `call_tool`: `capture_viewport`, `capture_status`, `capture_pair`, `capture_series`,
   `capture_bug`, `list_captures`, `build_contact_sheet_md`. See
   [docs/AGENT_USAGE.md](docs/AGENT_USAGE.md) and the optional Claude Code skill in
   [skill/SKILL.md](skill/SKILL.md).

Requirements: Unreal Engine 5.8 with the experimental Unreal MCP and Toolset Registry plugins.
Python only, nothing to compile. Status: the logic, the MCP layer and the plugin shell are tested
in CI against a fake `unreal` module; they have not yet been verified inside Unreal. The in-editor
check is `tests/ue_smoke.py` (see [docs/TESTING.md](docs/TESTING.md)).

## Install as a Python library

```sh
pip install trysac-ue-capture-toolset
# or
uv add trysac-ue-capture-toolset
```

Requires Python 3.10 or newer. No runtime dependencies. The import name is `ue_capture_toolset`.

## Usage

```python
from datetime import datetime

from ue_capture_toolset import capture_path, parse_resolution, recent_errors

print(parse_resolution("1920x1080"))  # (1920, 1080)
print(capture_path("Saved", label="hero shot", at=datetime(2026, 11, 8, 9, 5, 7)))
# Saved/Captures/2026-11-08/090507-hero-shot.png
print(recent_errors("LogTemp: Error: boom\nLogTemp: Warning: ok"))  # ['LogTemp: Error: boom']
```

Inside the Unreal editor, pass the `unreal` module as `ue` to the adapter functions (`capture_viewport`, `poll_capture`). These calls are verified only against a fake module, not inside Unreal.

`ue_capture_toolset.mcp` exposes the same operations with flat, JSON-friendly parameters and a JSON string result (first key `summary`; errors come back as `{"summary": "error: ...", "error": {...}}` instead of raising). It takes the Saved folder from `unreal.Paths.project_saved_dir()`, identifies captures by a `capture_id` (image path relative to Saved) and adds `capture_status`, a non-blocking check for the asynchronous `HighResShot`. The plugin's toolset class forwards to it.

## Public API

Core (pure, no `unreal` import):

- `parse_resolution(text) -> (width, height)`. Raises `CaptureError` `invalid_resolution`.
- `capture_path(saved_dir, label, at=None)`. Returns `<saved_dir>/Captures/<YYYY-MM-DD>/<HHMMSS>-<slug>.png`. Duplicates in the same second get a `~002`-style suffix. Raises `invalid_label` or `too_many_captures`.
- `read_git_commit(project_dir) -> str | None`. Reads `.git` files directly and never runs git. It inspects only the given folder.
- `recent_errors(log_text, limit=20) -> list[str]`. Returns the last `limit` lines containing `Error:`. Raises `input_too_large` above 8,000,000 characters.
- `build_bug_markdown(sidecar, *, severity, title, notes="", errors=(), image_link=None)`. Severity is one of `low`, `medium`, `high`, `critical`.
- `build_contact_sheet_md(sidecars, *, title="Contact sheet")`. Holds at most 200 captures.
- `CaptureError(code, message)`. `code` is a stable identifier such as `invalid_resolution`, `camera_not_found`, `capture_timeout`, `unknown_capture`, `invalid_sidecar`, `invalid_severity`, `invalid_series`, `invalid_path` or `input_too_large`.

Adapter (each function takes `ue` first):

- `capture_viewport(ue, saved_dir, label="viewport", resolution="1920x1080", *, camera=None)` returns a pending `Capture`; with `camera` (an actor label) the viewport pilots that actor first.
- `capture_pair(ue, saved_dir, before, ...)` requests an "after" capture from the transform of an earlier sidecar: it moves the viewport camera when `UnrealEditorSubsystem.set_level_viewport_camera_info` exists, otherwise it spawns a camera there (undoable transaction). The spawned actor stays in the level.
- `capture_series(ue, saved_dir, label, cameras, *, cursor=0, limit=50)` requests one capture per named camera (1 to 50 cameras) from `cursor`; `SeriesResult.cursor` is the next index or None.
- `cameras_with_tag(ue, tag)` returns the sorted labels of actors carrying an actor tag.
- `capture_bug(ue, saved_dir, title, severity="medium", ...)` captures the viewport and writes a Markdown report next to the image.
- `list_captures(ue, saved_dir, limit=100)` returns up to 500 sidecars, oldest first, and counts unreadable ones in `skipped`.
- `poll_capture(capture)` checks once for the file. It raises `capture_timeout` after `timeout_s` (default 30 seconds). It never sleeps.

Results are dataclasses with a `summary` field. Each sidecar is a JSON file; its `rotation` field is pitch, yaw, roll.

## Limits

- Requests are asynchronous (`HighResShot`); a capture is complete only when `poll_capture` returns `ready`.
- `read_git_commit` does not walk up to parent folders.
- `provenance.json` keeps only the last 100 entries.
- Video recording, image editing and uploads are not provided.

## Why not Unreal's built-in screenshot tools?

The built-in `HighResShot` command writes an image without a record of camera, map, quality or commit. This library calls that command and adds a sidecar with that context.

## Security

See [docs/SECURITY.md](docs/SECURITY.md) for the threat model.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
