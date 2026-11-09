# Python plugin shell with JSON string results, capture ids and an API compatibility layer

Status: accepted (pending verification in Unreal Engine 5.8)

## Context

The package must become an Unreal MCP toolset: a `unreal.ToolsetDefinition` subclass in a plugin's
`Content/Python/`, discovered by the Toolset Registry. The registry is experimental and its handling
of complex parameter and return types is not documented in detail. Tool calls run serially on the
game thread, while `HighResShot` writes its image frames after the request, so a tool cannot wait
for it. The adapter used the deprecated `EditorLevelLibrary`. Nothing can run in CI inside Unreal.

## Decision

- Ship a Python-only plugin (`plugin/CaptureToolset/`) whose toolset module only forwards to a new
  `mcp.py` layer. All behavior stays in the package, so it is covered by CI.
- Tools take primitive parameters (str, int, float); lists (cameras, captures) travel as JSON
  strings. Every tool returns a JSON string whose first key is `summary`; errors are returned as
  data, never raised to the agent.
- The MCP layer takes the Saved folder from `unreal.Paths.project_saved_dir()`; the agent never
  passes a file-system root. Captures are named by a `capture_id`, the image path relative to Saved.
- Capture tools return at once. `capture_status` is stateless: it rebuilds the `Capture` from the
  sidecar, uses the sidecar's modification time as the request time and calls `poll_capture` once.
  It survives editor restarts and module reloads. `capture_series` requests one camera per call and
  returns a `cursor`, so two shots are never requested in the same frame.
- `compat.py` resolves `UnrealEditorSubsystem`, `EditorActorSubsystem` and `LevelEditorSubsystem`
  first and falls back to `EditorLevelLibrary`. `capture_pair` prefers moving the viewport camera
  (`set_level_viewport_camera_info`) over spawning an actor; the spawn fallback runs inside
  `ScopedEditorTransaction` when available.
- No `dry_run` flag: captures only add new files under `Saved/Captures` and never modify assets.
- `tools/build_plugin.py` vendors the package into the plugin; no pip inside the editor.

## Consequences

The schema the agent sees is simple and certain to be supported, at the cost of the agent parsing
JSON from a string and polling. A capture whose sidecar was rewritten later gets a later timeout
start. The decorator order, the engine API names and whether HighResShot keeps the exact file name
are confirmed by the manual steps in `docs/TESTING.md`.
