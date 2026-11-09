# Testing

## Running

```sh
uv run python scripts/check.py           # every gate (lint, format, types, tests, docs...)
uv run pytest --cov=ue_capture_toolset   # tests with branch coverage report
uv run python tools/build_plugin.py      # build the Unreal plugin zip into dist/
```

## Policy

- Branch coverage of `src/ue_capture_toolset` must stay at or above 85 %.
- Tests exercise the public API and assert return values, raised `CaptureError` codes, the JSON
  returned by the MCP layer and the calls recorded on the fake `unreal` module.
- Tests use no network and do not depend on test order; core and adapter tests pass time as `at=`
  or `clock=`. MCP tests use real file timestamps (`os.utime`) for `capture_status` timeouts.
- Nothing in the test suite runs inside Unreal Engine.

## Tests in CI (no Unreal needed)

| File | What it covers |
|---|---|
| `tests/test_core.py` | Resolution parsing, capture path uniqueness and time ordering (Hypothesis), git reading from loose refs, packed-refs, detached HEAD and missing `.git`, log tail selection, bug and contact sheet goldens (`tests/golden/`). |
| `tests/test_adapter.py` | Adapter against `tests/fakes/unreal.py` (`FakeUnreal`, legacy `EditorLevelLibrary`): pair transforms within 1e-3, series cursor/limit, cameras by tag, bug reports, listing; plus `FakeUnreal58` (subsystems only) for camera captures and pairs via `set_level_viewport_camera_info`. |
| `tests/test_mcp.py` | MCP layer: `capture_bug` in editor mode and in PIE (legacy and UE 5.8 fakes, with and without a pawn, `is_in_play_in_editor` false), `hide_ui` accepted without effect, Saved folder from `unreal.Paths`, `capture_id` handling, `capture_status` pending/ready/timeout, errors returned as data, the UE 5.8 subsystem paths (with and without the viewport setter; spawn inside a transaction) and the legacy library path, list filters, contact sheets. |
| `tests/test_plugin_shell.py` | Loads `plugin/CaptureToolset/Content/Python/capture_toolset_mcp.py` with a fake `unreal` and a fake `toolset_registry`: every MCP function is a documented `tool_call` static method returning `str` with every parameter described, no `ue`/`saved_dir` parameter is exposed, and each tool forwards correctly. |
| `tests/test_build_plugin.py` | The plugin zip contains the `.uplugin`, the toolset module and the vendored package; the `.uplugin` depends on `PythonScriptPlugin` and `ToolsetRegistry` and its version matches the package. |
| `tests/test_ue_capture_toolset.py` | Version and public exports. |

## In-editor check (manual, Unreal Engine 5.8)

CI cannot run Unreal, so these steps are the acceptance test for the real engine. Never mark the
plugin as verified in Unreal without running them.

1. Install the plugin (README, "Install in Unreal Engine") in a blank UE 5.8 project with at least
   one `CameraActor` labelled `CamA` and tagged `Portfolio`.
2. Compare the decorator order in `capture_toolset_mcp.py` (`@staticmethod` above
   `@toolset_registry.tool_call`) with the engine's own example,
   `Engine/Plugins/Experimental/ToolsetRegistry/Content/Python/toolset_registry/toolsets/core/actor.py`,
   and match it if it differs.
3. Enable Python *Developer Mode* (Editor Preferences > Plugins > Python), restart, and check in
   `Intermediate/PythonStub/unreal.py` that these exist: `UnrealEditorSubsystem.get_editor_world`,
   `UnrealEditorSubsystem.get_level_viewport_camera_info`,
   `UnrealEditorSubsystem.set_level_viewport_camera_info`, `EditorActorSubsystem.get_all_level_actors`,
   `EditorActorSubsystem.spawn_actor_from_class`, `LevelEditorSubsystem.pilot_level_actor`,
   `Actor.actor_has_tag`, `ScopedEditorTransaction`, `Paths.project_saved_dir`,
   `Paths.convert_relative_path_to_full`, `SystemLibrary.get_console_variable_int_value` and
   `SystemLibrary.execute_console_command`.
4. Run `py "<repo>/tests/ue_smoke.py"` in the Output Log (Python). Wait until the log prints
   `[smoke] u802-ue-capture-toolset: ...`, then open `Saved/Smoke/u802-ue-capture-toolset.json`:
   `finished` must be true and every step must have `"ok": true`.
5. From the agent: `list_toolsets` shows `CaptureTools`; `describe_toolset` lists seven tools with
   their parameter descriptions.
6. Captures in the editor: `capture_viewport` at `1920x1080` and at `1280x720`, then
   `capture_status` until ready. Open each PNG: its size must equal the requested resolution and the
   image file name must be exactly the `capture_id` (HighResShot must not add a suffix). Check the
   sidecar fields (map, transform, `sg.*`, commit, time).
7. From a camera by name: `capture_viewport` with `camera: "CamA"`; the image shows that camera's
   view and the sidecar transform matches the actor.
8. Pair: move the viewport, call `capture_pair` with the first capture; the two images must match
   and the sidecar transforms differ by less than 1e-3. Note whether the viewport path or the
   spawned `Pair_after` actor was used; Ctrl+Z removes a spawned actor.
9. Series: `capture_series` with `tag: "Portfolio"`, polling and following `cursor`; every image
   shows its own camera.
10. Bug: `capture_bug` after triggering an `Error:` in the log; the Markdown lists the last error
    lines (up to 20).
11. PIE: start Play In Editor and repeat step 6; note any difference (HighResShot behaves
    differently in PIE; the world recorded in the sidecar is the editor world). Then call
    `capture_bug` during PIE: `mode` must be `pie` and `player_location`/`player_rotation` must
    match the player pawn; stop PIE and repeat: `mode` must be `editor` with null player fields.
    Check that `LevelEditorSubsystem.is_in_play_in_editor`, `UnrealEditorSubsystem.get_game_world`
    and `GameplayStatics.get_player_pawn` exist in the Python stub.
12. `hide_ui` (currently a no-op): capture the same view with `hide_ui` true and false and confirm
    the images are identical and contain no editor UI. Check whether any `HighResShot` option or
    `ShowFlag.*` console variable reliably hides gizmos and selection outlines; if so, implement it
    and remove the no-op note from `docs/AGENT_USAGE.md`.
13. Record the date, engine version and result in `docs/PROJECT.md`. Delete the test captures under
    `Saved/Captures` and any `Pair_*` actors by hand if you do not want to keep them.

## Not covered

Video recording, image comparison, captures of the game world in PIE beyond step 11, and behavior on
engine versions other than 5.8.
