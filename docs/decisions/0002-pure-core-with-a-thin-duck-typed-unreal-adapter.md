# Pure core with a thin duck-typed Unreal adapter

Status: accepted (generated, pending human review)

## Context

Agents need reproducible Unreal captures with context. Unreal's Python API is only available inside the editor and runs on the game thread, while HighResShot completes asynchronously.

## Decision

Keep all logic (resolution, paths, sidecars, git reading, log scanning, Markdown) in a pure core that never imports unreal. A thin adapter takes the unreal module (or a fake) as its first argument, returns pending Capture results, and exposes poll_capture that checks the file against an injected clock instead of sleeping. Capture names use a process-wide bounded reservation table with a ~NNN suffix so they stay unique and time-sortable. The git commit is read directly from .git files.

## Consequences

The core and adapter are unit-testable without Unreal and use only the standard library. The real UE API calls are unverified until a supervised smoke test runs in the editor. Uniqueness within one process relies on the reservation table (bounded, evicting oldest) plus on-disk checks.
