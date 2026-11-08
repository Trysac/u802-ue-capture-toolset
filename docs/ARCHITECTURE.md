# Architecture

## Purpose

`trysac-ue-capture-toolset` is a small Python library with a pure core (`ue_capture_toolset.core`) and a thin Unreal adapter (`ue_capture_toolset.adapter`). It produces reproducible captures with JSON sidecars, Markdown bug reports and contact sheets.

## Shape

```text
caller code --> ue_capture_toolset (public API in __init__.py)
                    |
                    +-- core/: pure functions, never imports unreal
                    +-- adapter.py: takes `ue` first (the unreal module or a fake)
```

- **Public API**: the names listed in `__all__` of `src/ue_capture_toolset/__init__.py`.
- **Core modules**: `resolution`, `paths`, `sidecar`, `gitinfo`, `logscan`, `markdown`, `errors`.
- **Adapter**: `HighResShot` is asynchronous. Capture functions return a pending `Capture`, and `poll_capture` checks for the file against a deadline. Nothing sleeps on the game thread.
- **Errors**: failures raise `CaptureError` with a stable `code`.
- **Side effects**: the adapter writes sidecars and reports under the given Saved folder and spawns camera actors. Nothing is deleted.

## Decisions

No ADR directory is present in this repository.
