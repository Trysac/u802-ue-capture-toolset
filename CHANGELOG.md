# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-11-08

### Added

- Unreal plugin `plugin/CaptureToolset/` (Python only): `CaptureTools` toolset registered in the Toolset Registry with seven documented tools (`capture_viewport`, `capture_status`, `capture_pair`, `capture_series`, `capture_bug`, `list_captures`, `build_contact_sheet_md`).
- `mcp` module: flat parameters, JSON string results with `summary` first, errors returned as data, Saved folder taken from `unreal.Paths`, `capture_id` handles and a non-blocking `capture_status`.
- `compat` module: prefers `UnrealEditorSubsystem`, `EditorActorSubsystem` and `LevelEditorSubsystem`, falls back to `EditorLevelLibrary`; `capture_pair` uses `set_level_viewport_camera_info` when available.
- Adapter: `capture_viewport(camera=...)`, `capture_series(cursor=..., limit=...)` with `SeriesResult.cursor`, `cameras_with_tag`.
- `tools/build_plugin.py` (plugin zip with the vendored package), `tests/ue_smoke.py` (in-editor check), `skill/SKILL.md`, ADR 0003.

### Changed

- The pair camera fallback is spawned inside `ScopedEditorTransaction` when available (undoable).
- `docs/AGENT_USAGE.md` describes real `call_tool` usage; `docs/TESTING.md` lists the in-editor acceptance steps.

## [0.1.0] - 2026-11-08

### Added

- Add the pure capture core (resolution, paths, sidecars, git commit reader, log scan, Markdown reports and contact sheets) and a thin Unreal adapter with viewport, pair, series and bug captures.
- Initial project structure from the factory utility template.
