# Agent usage

This page shows how an agent is expected to call the capture toolset once the Unreal MCP plugin
wraps it. The plugin packaging (`.uplugin`, `ToolsetDefinition` class) is not part of this
repository yet, so the request and response bodies below are illustrative shapes of the Python
results, not recorded sessions. The adapter has only been exercised against a fake `unreal`
module; nothing here was tested inside Unreal.

All paths live under the project's `Saved/` folder. Nothing is deleted. `HighResShot` is
asynchronous: capture tools return `status: "pending"`, and the agent calls a poll tool
(`poll_capture`) on later turns until `status` is `ready` or the error code `capture_timeout`
appears.

## capture_viewport

Request:

```json
{"tool": "capture_viewport", "arguments": {"label": "hero shot", "resolution": "1920x1080"}}
```

Response:

```json
{"status": "pending", "image_path": "Saved/Captures/2026-11-08/090507-hero-shot.png", "summary": "Requested 1920x1080 capture of viewport: pending 090507-hero-shot.png"}
```

A sidecar `090507-hero-shot.json` is written next to the image with the map, camera, location,
rotation (pitch, yaw, roll), `sg.*` quality groups, git commit and capture time.

## capture_pair

```json
{"tool": "capture_pair", "arguments": {"before": "Captures/2026-11-08/090507-hero-shot.png", "label": "after"}}
```

A new camera actor is spawned at the transform stored in the before sidecar, and the after image
is requested from it. The actor stays in the level.

## capture_series

```json
{"tool": "capture_series", "arguments": {"label": "tour", "cameras": ["CamA", "CamB"]}}
```

Every camera label is checked first; a missing one fails with `camera_not_found` before any shot.

## capture_bug

```json
{"tool": "capture_bug", "arguments": {"title": "Player falls through floor", "severity": "high"}}
```

Writes a Markdown report next to the image with the context, the last 20 `Error:` log lines and
the notes.

## list_captures and contact sheets

`list_captures` returns the newest sidecars, oldest first. `build_contact_sheet_md` renders them
as Markdown that links each image without opening it.

## Errors

Every failure is a `CaptureError` with a stable `code`: `invalid_resolution`, `camera_not_found`,
`capture_timeout`, `unknown_capture`, `invalid_label`, `invalid_path`, `invalid_sidecar`,
`invalid_severity`, `invalid_series`, `too_many_captures`, `input_too_large`.
