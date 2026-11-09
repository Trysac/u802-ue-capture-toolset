---
name: ue-capture
description: Take reproducible Unreal Engine 5.8 editor screenshots through the CaptureTools MCP toolset — each with a JSON sidecar (map, camera transform, sg.* preset, git commit) — for dev logs, bug reports, exact before/after pairs, camera tours and Markdown contact sheets. Use whenever visual evidence of the level is needed.
---
# Captures (Unreal MCP toolset `CaptureTools`)

Requires the Capture Toolset plugin enabled and the Unreal MCP server connected.

1. **Shoot:** `call_tool` → `CaptureTools.capture_viewport` (`label`, optional `camera` actor label).
   Keep the returned `capture_id`.
2. **Wait:** `capture_status` with the `capture_id` until `done` is true (HighResShot writes the
   image a few frames later). Never start another capture while one is `pending`.
3. **Before/after:** after a change, `capture_pair` with `before` = the earlier `capture_id`; the
   new shot uses the exact same transform. Poll it.
4. **Tour:** `capture_series` with `tag` (for example `Portfolio`) or `cameras_json`; one camera per
   call: poll the capture, then call again with the returned `cursor` until it is `null`.
5. **Bug:** `capture_bug` (`title`, `severity`, `notes`); paste `markdown` into `bugs.md`.
6. **Dev log:** `list_captures` (`since`, `label`) then `build_contact_sheet_md` with the ids.

Rules: one MCP call at a time; captures only add files under `Saved/Captures`; if a result has
`error`, read `error.code` and fix the input instead of retrying blindly; a `timeout` status means
the image never appeared (check the editor viewport is visible), not that it is still coming.
