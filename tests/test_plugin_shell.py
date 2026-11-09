"""The Content/Python toolset module forwards every tool to the MCP layer with ``unreal``."""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from fakes.unreal import FakeUnreal

ROOT = Path(__file__).resolve().parents[1]
SHELLS = sorted((ROOT / "plugin").glob("*/Content/Python/*_mcp.py"))


@pytest.fixture
def shell(monkeypatch: pytest.MonkeyPatch, saved: Path) -> Any:
    fake = FakeUnreal()
    fake.saved_dir = str(saved)
    fake.uclass = lambda: lambda cls: cls  # type: ignore[attr-defined]
    fake.ToolsetDefinition = type("ToolsetDefinition", (), {})  # type: ignore[attr-defined]
    registry = types.ModuleType("toolset_registry")
    registry.tool_call = lambda fn: setattr(fn, "is_tool", True) or fn  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "unreal", fake)
    monkeypatch.setitem(sys.modules, "toolset_registry", registry)
    assert len(SHELLS) == 1
    spec = importlib.util.spec_from_file_location("shell_under_test", SHELLS[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, fake


def _toolset(module: Any) -> Any:
    classes = [
        c for _, c in inspect.getmembers(module, inspect.isclass) if c.__module__ == module.__name__
    ]
    assert len(classes) == 1
    return classes[0]


def test_every_mcp_function_is_a_documented_tool(shell: Any) -> None:
    module, _ = shell
    toolset = _toolset(module)
    assert toolset.__name__ == "CaptureTools"
    assert inspect.getdoc(toolset)
    from ue_capture_toolset import mcp

    public = {
        n
        for n, f in inspect.getmembers(mcp, inspect.isfunction)
        if f.__module__ == mcp.__name__ and not n.startswith("_") and n != "to_json"
    }
    tools = {n for n, f in vars(toolset).items() if isinstance(f, staticmethod)}
    assert public == tools
    for name in tools:
        fn = getattr(toolset, name)
        assert getattr(fn, "is_tool", False), name
        doc = inspect.getdoc(fn) or ""
        assert "Args:" in doc or not inspect.signature(fn).parameters, name
        assert "Returns:" in doc, name
        params = inspect.signature(fn).parameters
        for param in params:
            assert param in doc, (name, param)
        assert inspect.signature(fn).return_annotation in (str, "str")
        assert "ue" not in params and "saved_dir" not in params


def test_tools_forward_with_unreal(shell: Any) -> None:
    module, fake = shell
    toolset = _toolset(module)
    fake.add_camera("CamA", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    shot = json.loads(toolset.capture_viewport("hero"))
    assert shot["status"] == "pending"
    assert json.loads(toolset.capture_status(shot["capture_id"]))["pending"] == 1
    assert json.loads(toolset.capture_pair(shot["capture_id"]))["before_id"] == shot["capture_id"]
    assert json.loads(toolset.capture_series("tour", '["CamA"]'))["cursor"] is None
    assert json.loads(toolset.capture_bug("Bug", "low"))["markdown"].startswith("# Bug")
    listed = json.loads(toolset.list_captures())
    assert len(listed["captures"]) == 4
    sheet = json.loads(toolset.build_contact_sheet_md(json.dumps([shot["capture_id"]])))
    assert sheet["count"] == 1
    assert len(fake.commands) == 4
