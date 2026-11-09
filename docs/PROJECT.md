# Project record

## Objective

Provide reproducible Unreal Engine 5.8 captures for agents, each with a JSON sidecar recording camera, map, quality preset and git commit, plus Markdown bug reports and contact sheets. The core is testable without Unreal.

## Scope

- In scope: resolution parsing, unique time-sortable capture paths, sidecars, reading git HEAD without running git, scanning logs for errors, Markdown rendering, and a thin adapter over the Unreal Python API that takes the `unreal` module as an argument.
- In scope since 0.2.0: the Unreal plugin (`.uplugin`, `ToolsetDefinition` shell), the `mcp` layer with `capture_status`, cameras by tag, series with a cursor, and the subsystem compatibility layer.
- Out of scope: video recording, image editing and uploads. Adapter and plugin behaviour is verified only against a fake module until the in-editor check is run.

## Timeline

| Date | Event |
|---|---|
| 2026-11-08 | Repository created from the factory utility template; factory run (core + adapter). |
| 2026-11-08 | Interactive session (Claude Code): plugin shell, `mcp` layer, `capture_status`, compat layer, build tool, smoke test, skill, docs (0.2.0). Not yet verified inside Unreal. |
| pending | In-editor verification on UE 5.8 (`docs/TESTING.md`): date, engine version, smoke result. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 342150 / 211905 |
| Hours (human) | pending measurement |
| Cost (USD) | 1.2826 |

## Factory run u802 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2198 | 128000 | 0 | 5188 | 0.6427 |
| generation | claude-sonnet-5-5 | yes | 2198 | 73403 | 0 | 5188 | 0.3697 |
| fix-1 | claude-sonnet-5-5 | no | 8 | 731 | 15939 | 45798 | 0.0518 |
| audit | claude-sonnet-5-5 | no | 14 | 4878 | 55575 | 184914 | 0.2062 |
| fix-2 | claude-sonnet-5-5 | no | 0 | 0 | 0 | 0 | 0.0000 |
| docs | claude-haiku-5-5 | no | 96644 | 4893 | 0 | 0 | 0.0121 |

Total: $1.2826. Prices: Anthropic list prices.
