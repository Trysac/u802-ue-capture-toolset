# Architecture

## Purpose

`trysac-ue-capture-toolset` is a small Python library with a pure core (`ue_capture_toolset.core`) and a thin Unreal adapter (`ue_capture_toolset.adapter`). It produces reproducible captures with JSON sidecars, Markdown bug reports and contact sheets.

## Shape

```text
AI agent --MCP--> Unreal MCP server --> Toolset Registry
                                            |
   plugin/CaptureToolset/Content/Python/capture_toolset_mcp.py  (CaptureTools)
                                            |  forwards with the real unreal module
                                            v
   ue_capture_toolset.mcp      flat params in, JSON string out, errors as data,
                               Saved folder from unreal.Paths, capture ids
                                            v
   ue_capture_toolset.adapter  functions that receive the unreal module as ue
          |                 \
          v                  compat.py  subsystem-or-legacy API resolution
   core/  pure logic, never imports unreal
```

- **Public API**: the names listed in `__all__` of `src/ue_capture_toolset/__init__.py`.
- **Core modules**: `resolution`, `paths`, `sidecar`, `gitinfo`, `logscan`, `markdown`, `errors`.
- **Adapter**: `HighResShot` is asynchronous. Capture functions return a pending `Capture`, and `poll_capture` checks for the file against a deadline. Nothing sleeps on the game thread.
- **MCP layer** (`mcp.py`): derives the Saved folder from `unreal.Paths.project_saved_dir()`, names captures by a `capture_id` (image path relative to Saved), and adds `capture_status`, a stateless check that rebuilds a `Capture` from the sidecar (its file time is the request time) and calls `poll_capture`.
- **Errors**: failures raise `CaptureError` with a stable `code`; the MCP layer returns them as JSON data.
- **Side effects**: the adapter writes sidecars and reports under the given Saved folder and spawns camera actors. Nothing is deleted.

## Unreal integration

- `plugin/CaptureToolset/CaptureToolset.uplugin` declares a Python-only editor plugin that depends
  on `PythonScriptPlugin` and `ToolsetRegistry`.
- `plugin/CaptureToolset/Content/Python/capture_toolset_mcp.py` defines
  `CaptureTools(unreal.ToolsetDefinition)`; each tool is a static method marked with
  `@toolset_registry.tool_call`, with Google-style docstrings that the registry turns into the tool
  schema. It contains no logic: it forwards to `mcp.py`.
- Tool calls run serially on the game thread, so no tool waits: captures return a pending
  `capture_id`, `capture_status` checks once, and `capture_series` requests one camera per call
  with a `cursor`.
- `tools/build_plugin.py` copies the plugin and vendors the package into `Content/Python/` so the
  editor's Python can import it without pip.
- `compat.py` prefers `UnrealEditorSubsystem`, `EditorActorSubsystem` and `LevelEditorSubsystem`
  and falls back to the deprecated `EditorLevelLibrary`; `capture_pair` moves the viewport camera
  with `set_level_viewport_camera_info` when present and otherwise spawns a camera actor inside a
  `ScopedEditorTransaction`.
- The real-engine check is `tests/ue_smoke.py` plus the manual steps in `docs/TESTING.md`. The
  plugin is tested in CI against fakes only and has not yet been verified inside Unreal.

## Decisions

See `docs/decisions/` (0002: pure core with a thin duck-typed adapter; 0003: plugin shell, JSON
results, asynchronous capture ids and API compatibility).
