"""In-editor smoke test (NOT collected by pytest). Run inside Unreal Editor 5.8 with the plugin on.

Output Log > Cmd > Python:  py "<repo>/tests/ue_smoke.py"
It writes ``<Project>/Saved/Smoke/u802-ue-capture-toolset.json`` with one entry per step. Because
HighResShot is asynchronous, capture steps run one at a time from a Slate post-tick callback: each
waits (without blocking the game thread) until the previous capture is ready or timed out. The
report is rewritten after every step; ``finished`` is true at the end.
It only writes new files under Saved/Captures and Saved/Smoke and may leave one camera actor named
``Pair_smoke-after`` in the level (legacy path); it never deletes anything.
"""

import json
import time
import traceback
from pathlib import Path

import unreal

REPO = "u802-ue-capture-toolset"
TIMEOUT_S = 30.0


def main() -> None:
    from ue_capture_toolset import compat, mcp

    saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
    out_dir = saved / "Smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{REPO}.json"
    results = []
    state = {"pending": None, "ids": [], "handle": None, "started": time.time()}

    def write(finished):
        report = {
            "repo": REPO,
            "engine": unreal.SystemLibrary.get_engine_version(),
            "saved_dir": str(saved),
            "finished": finished,
            "passed": sum(r["ok"] for r in results),
            "total": len(results),
            "steps": results,
        }
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    def step(name, fn):
        started = time.time()
        try:
            value = fn()
            parsed = json.loads(value) if isinstance(value, str) else value
            ok = not (isinstance(parsed, dict) and "error" in parsed)
            results.append({"step": name, "ok": ok, "result": parsed})
        except Exception:  # the smoke test records every failure instead of stopping
            parsed = None
            results.append({"step": name, "ok": False, "error": traceback.format_exc()[-2000:]})
        results[-1]["seconds"] = round(time.time() - started, 3)
        write(False)
        return parsed

    def shot(name, fn):
        parsed = step(name, fn)
        if isinstance(parsed, dict):
            capture_id = parsed.get("capture_id")
            if capture_id is None and parsed.get("captures"):
                capture_id = parsed["captures"][0]["capture_id"]
            if capture_id:
                state["pending"] = capture_id
                state["ids"].append(capture_id)

    def first_id():
        return state["ids"][0] if state["ids"] else "Captures/missing.png"

    step("api: editor", lambda: {"api": type(compat.editor_api(unreal)).__name__})
    step("api: actors", lambda: {"api": type(compat.actor_api(unreal)).__name__})
    step("api: level", lambda: {"api": type(compat.level_api(unreal)).__name__})
    step(
        "api: set_level_viewport_camera_info",
        lambda: {
            "present": hasattr(
                unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem),
                "set_level_viewport_camera_info",
            )
        },
    )
    step("toolset module imports", lambda: {"module": __import__("capture_toolset_mcp").__name__})

    queue = [
        lambda: shot("capture_viewport", lambda: mcp.capture_viewport(unreal, "smoke viewport")),
        lambda: shot("capture_pair", lambda: mcp.capture_pair(unreal, first_id(), "smoke-after")),
        lambda: shot(
            "capture_bug", lambda: mcp.capture_bug(unreal, "Smoke bug", "low", "from ue_smoke.py")
        ),
        lambda: step("list_captures", lambda: mcp.list_captures(unreal, 10, label="smoke")),
        lambda: step(
            "build_contact_sheet_md",
            lambda: mcp.build_contact_sheet_md(unreal, json.dumps(state["ids"]), "Smoke"),
        ),
    ]

    def tick(_delta):
        try:
            if state["pending"] is not None:
                status = json.loads(mcp.capture_status(unreal, state["pending"], TIMEOUT_S))
                if status.get("pending"):
                    return
                ok = status.get("ready") == 1
                results.append({"step": f"ready: {state['pending']}", "ok": ok, "result": status})
                state["pending"] = None
                write(False)
                return
            if queue:
                queue.pop(0)()
                return
        except Exception:  # never leave the callback registered on failure
            results.append({"step": "tick", "ok": False, "error": traceback.format_exc()[-2000:]})
        unreal.unregister_slate_post_tick_callback(state["handle"])
        report = write(True)
        unreal.log(f"[smoke] {REPO}: {report['passed']}/{report['total']} ok -> {target}")

    write(False)
    state["handle"] = unreal.register_slate_post_tick_callback(tick)


main()
