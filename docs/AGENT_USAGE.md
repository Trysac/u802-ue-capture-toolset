# Agent usage

Once the plugin is enabled, the Unreal MCP server lists the toolset `CaptureTools`. With the
default *tool search* mode the agent sees three meta-tools: `list_toolsets`, `describe_toolset` and
`call_tool`. Calls run one at a time on the editor's game thread: never issue them in parallel.

Every tool returns a JSON string. The first key is always `summary` (one line). Errors are data:
`{"summary": "error: ...", "error": {"code": "...", "message": "..."}}` with codes
`invalid_resolution`, `invalid_label`, `camera_not_found`, `unknown_capture`, `invalid_series`,
`invalid_severity`, `invalid_sidecar`, `invalid_path`, `invalid_json`, `invalid_filter`,
`invalid_timeout`, `too_many_captures`, `input_too_large`, `io_error` or `unreal_error`.

The Saved folder is taken from the editor (`unreal.Paths.project_saved_dir()`); the agent never
passes it. A `capture_id` is the image path relative to Saved, for example
`Captures/2026-11-08/090507-hero-shot.png`. Tools that take a capture also accept the absolute
image, sidecar (`.json`) or bug report (`.md`) path, as long as it is under `Saved/Captures`.
Nothing is deleted.

The responses below show the shape produced by the MCP layer in CI against a fake `unreal` module;
they are not recorded from a real editor session.

## HighResShot is asynchronous

Capture tools return immediately with `status: "pending"`. The image appears a few frames later.
Call `capture_status` on the next turn until `done` is `true`, and do not request the next capture
while one is pending (two shots requested in the same frame can overwrite each other).

## capture_viewport

```json
{"toolset": "CaptureTools", "tool": "capture_viewport", "arguments": {
  "label": "hero shot", "resolution": "1920x1080", "camera": ""}}
```

```json
{"summary": "Requested 1920x1080 capture of viewport: pending 090507-hero-shot.png",
 "capture_id": "Captures/2026-11-08/090507-hero-shot.png", "status": "pending",
 "camera": "viewport", "resolution": "1920x1080",
 "image_path": "C:/Proj/Saved/Captures/2026-11-08/090507-hero-shot.png",
 "sidecar_path": "C:/Proj/Saved/Captures/2026-11-08/090507-hero-shot.json"}
```

With `camera` set to an actor label (for example `"CamHero"`), the viewport pilots that actor
first. The sidecar records map, camera, location, rotation (pitch, yaw, roll), the `sg.*` quality
groups, the git commit (read from `.git` without running git) and the capture time.

## capture_status

```json
{"toolset": "CaptureTools", "tool": "capture_status", "arguments": {
  "capture": "Captures/2026-11-08/090507-hero-shot.png"}}
```

```json
{"summary": "1 of 1 ready", "done": true, "ready": 1, "pending": 0, "timeout": 0,
 "captures": [{"capture_id": "Captures/2026-11-08/090507-hero-shot.png", "status": "ready",
               "image_path": "C:/Proj/Saved/Captures/2026-11-08/090507-hero-shot.png"}]}
```

`capture` can also be a JSON list of ids. A capture whose image has not appeared `timeout_s`
seconds (default 30) after its sidecar was written is reported as `timeout`.

## capture_pair

```json
{"toolset": "CaptureTools", "tool": "capture_pair", "arguments": {
  "before": "Captures/2026-11-08/090507-hero-shot.png", "label": "after", "resolution": ""}}
```

```json
{"summary": "Pair: before Captures/2026-11-08/090507-hero-shot.png, after 101500-after.png (pending)",
 "capture_id": "Captures/2026-11-08/101500-after.png", "status": "pending", "camera": "viewport",
 "resolution": "1920x1080", "image_path": "...", "sidecar_path": "...",
 "before_id": "Captures/2026-11-08/090507-hero-shot.png"}
```

When the editor exposes `UnrealEditorSubsystem.set_level_viewport_camera_info` the viewport camera
is moved to the recorded transform (`camera: "viewport"`). Otherwise a `CameraActor` named
`Pair_<label>` is spawned there inside an undoable transaction and piloted; it stays in the level.

## capture_series

```json
{"toolset": "CaptureTools", "tool": "capture_series", "arguments": {
  "label": "portfolio", "tag": "Portfolio", "cursor": 0}}
```

```json
{"summary": "Requested 1 captures for series 'portfolio', 2 cameras left",
 "cameras": ["CamBridge", "CamCastle", "CamDocks"],
 "captures": [{"summary": "...", "capture_id": "Captures/2026-11-08/110000-portfolio-cambridge.png",
               "status": "pending", "camera": "CamBridge", "resolution": "1920x1080",
               "image_path": "...", "sidecar_path": "..."}],
 "cursor": 1}
```

Give either `tag` (actor tag shared by the cameras; sorted by label) or `cameras_json`
(`"[\"CamA\", \"CamB\"]"`). Every camera is checked before any shot (`camera_not_found`). One camera
per call: poll the capture, then call again with the returned `cursor` until it is `null`.

## capture_bug

```json
{"toolset": "CaptureTools", "tool": "capture_bug", "arguments": {
  "title": "Player falls through floor", "severity": "high", "notes": "Walk left from spawn"}}
```

```json
{"summary": "Bug report (high) with 3 recent errors: 120000-bug.md",
 "capture_id": "Captures/2026-11-08/120000-bug.png", "status": "pending", "camera": "viewport",
 "resolution": "1920x1080", "image_path": "...", "sidecar_path": "...",
 "report_path": "C:/Proj/Saved/Captures/2026-11-08/120000-bug.md", "error_count": 3,
 "markdown": "# Bug: Player falls through floor\n\n- **Severity:** high\n..."}
```

The report holds map, camera, transform, resolution, commit, quality preset, the last 20 `Error:`
lines of the newest `Saved/Logs/*.log`, provenance (from `Saved/provenance.json`, if any) and notes.

## list_captures

```json
{"toolset": "CaptureTools", "tool": "list_captures", "arguments": {
  "limit": 20, "since": "2026-11-08", "label": "hero"}}
```

```json
{"summary": "2 of 2 matching captures, 0 skipped",
 "captures": [{"capture_id": "Captures/2026-11-08/090507-hero-shot.png", "label": "hero shot",
               "map": "/Game/Maps/Arena.Arena", "camera": "viewport",
               "captured_at": "2026-11-08T09:05:07", "resolution": "1920x1080",
               "git_commit": "0123456789abcdef0123456789abcdef01234567"}],
 "skipped": 0}
```

## build_contact_sheet_md

```json
{"toolset": "CaptureTools", "tool": "build_contact_sheet_md", "arguments": {
  "captures_json": "[\"Captures/2026-11-08/090507-hero-shot.png\", \"Captures/2026-11-08/101500-after.png\"]",
  "title": "Day 3"}}
```

```json
{"summary": "contact sheet with 2 captures (412 chars)",
 "content": "# Day 3\n\n2 captures.\n\n## 1. hero shot\n\n![hero shot](Captures/2026-11-08/090507-hero-shot.png)\n...",
 "count": 2}
```

Image links are relative to the Saved folder; images are never opened or modified.
