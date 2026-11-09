"""The MCP layer: JSON in, JSON out, errors as data, Saved folder from ``unreal.Paths``."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fakes.unreal import FakeUnreal, FakeUnreal58, LevelEditorSubsystem

from ue_capture_toolset import compat, mcp


def _load(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    assert next(iter(data)) == "summary"
    return data


@pytest.fixture
def fake(saved: Path) -> FakeUnreal:
    ue = FakeUnreal()
    ue.saved_dir = str(saved)
    return ue


@pytest.fixture
def fake58(saved: Path) -> FakeUnreal58:
    ue = FakeUnreal58()
    ue.saved_dir = str(saved)
    return ue


def test_capture_viewport_returns_pending_id_under_saved(fake: FakeUnreal, saved: Path) -> None:
    data = _load(mcp.capture_viewport(fake, "hero shot"))
    assert data["status"] == "pending"
    assert data["capture_id"].startswith("Captures/")
    assert data["capture_id"].endswith("-hero-shot.png")
    assert Path(data["sidecar_path"]).is_file()
    assert Path(data["image_path"]).resolve().is_relative_to(saved.resolve())
    assert data["resolution"] == "1920x1080"
    assert len(fake.commands) == 1


def test_saved_dir_without_converter(fake: FakeUnreal, saved: Path) -> None:
    fake.Paths = SimpleNamespace(project_saved_dir=lambda: str(saved))  # type: ignore[assignment]
    data = _load(mcp.capture_viewport(fake, "plain"))
    assert data["status"] == "pending"


def test_status_pending_then_ready(fake: FakeUnreal) -> None:
    shot = _load(mcp.capture_viewport(fake, "a"))
    pending = _load(mcp.capture_status(fake, shot["capture_id"]))
    assert pending["done"] is False and pending["pending"] == 1
    assert "call again" in pending["summary"]
    Path(shot["image_path"]).write_bytes(b"png")
    ready = _load(mcp.capture_status(fake, shot["sidecar_path"]))
    assert ready["done"] is True and ready["ready"] == 1
    assert ready["captures"][0]["capture_id"] == shot["capture_id"]


def test_status_timeout_and_list(fake: FakeUnreal) -> None:
    first = _load(mcp.capture_viewport(fake, "old"))
    second = _load(mcp.capture_viewport(fake, "new"))
    stale = time.time() - 120
    os.utime(first["sidecar_path"], (stale, stale))
    Path(second["image_path"]).write_bytes(b"png")
    refs = json.dumps([first["capture_id"], second["capture_id"]])
    data = _load(mcp.capture_status(fake, refs, timeout_s=30))
    assert data["timeout"] == 1 and data["ready"] == 1 and data["done"] is True
    assert "timed out" in data["summary"]


@pytest.mark.parametrize(
    ("ref", "timeout", "code"),
    [
        ("Captures/missing.png", 30.0, "unknown_capture"),
        ("../outside.png", 30.0, "unknown_capture"),
        ("Captures/x.txt", 30.0, "unknown_capture"),
        ("", 30.0, "unknown_capture"),
        ("[1, 2]", 30.0, "invalid_json"),
        ("[]", 30.0, "invalid_json"),
        ("[bad", 30.0, "invalid_json"),
        ("Captures/a.png", 0.0, "invalid_timeout"),
    ],
)
def test_status_errors_come_back_as_data(
    fake: FakeUnreal, ref: str, timeout: float, code: str
) -> None:
    data = _load(mcp.capture_status(fake, ref, timeout))
    assert data["error"]["code"] == code
    assert data["summary"].startswith("error:")


def test_capture_viewport_from_named_camera(fake: FakeUnreal) -> None:
    fake.add_camera("CamHero", (1.0, 2.0, 3.0), (5.0, 6.0, 7.0))
    data = _load(mcp.capture_viewport(fake, "hero", camera="CamHero"))
    assert data["camera"] == "CamHero"
    assert [a.get_actor_label() for a in fake.piloted] == ["CamHero"]
    missing = _load(mcp.capture_viewport(fake, "hero", camera="Nope"))
    assert missing["error"]["code"] == "camera_not_found"


def test_pair_legacy_spawns_camera(fake: FakeUnreal) -> None:
    before = _load(mcp.capture_viewport(fake, "before", "1280x720"))
    data = _load(mcp.capture_pair(fake, before["capture_id"]))
    assert data["before_id"] == before["capture_id"]
    assert data["camera"] == "Pair_after"
    assert data["resolution"] == "1280x720"
    assert len(fake.actors) == 1


def test_pair_ue58_moves_viewport_without_spawning(fake58: FakeUnreal58) -> None:
    before = _load(mcp.capture_viewport(fake58, "before"))
    data = _load(mcp.capture_pair(fake58, before["capture_id"], "after", "800x600"))
    assert data["camera"] == "viewport"
    assert fake58.actors == []
    assert len(fake58.viewport_moves) == 1
    assert data["resolution"] == "800x600"


def test_pair_ue58_without_setter_spawns_in_transaction(saved: Path) -> None:
    ue = FakeUnreal58(viewport_setter=False)
    ue.saved_dir = str(saved)
    before = _load(mcp.capture_viewport(ue, "before"))
    data = _load(mcp.capture_pair(ue, before["capture_id"]))
    assert data["camera"] == "Pair_after"
    assert len(ue.actors) == 1 and ue.piloted == ue.actors
    assert ue.transactions == ["Capture pair camera Pair_after"]
    assert compat.set_viewport_camera(ue, None, None) is False


def test_series_one_camera_per_call(fake58: FakeUnreal58) -> None:
    fake58.add_camera("CamA", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    fake58.add_camera("CamB", (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
    cameras = json.dumps(["CamA", "CamB"])
    first = _load(mcp.capture_series(fake58, "tour", cameras))
    assert first["cursor"] == 1 and len(first["captures"]) == 1
    assert "1 cameras left" in first["summary"]
    second = _load(mcp.capture_series(fake58, "tour", cameras, cursor=1))
    assert second["cursor"] is None
    assert second["captures"][0]["camera"] == "CamB"
    assert len(fake58.commands) == 2


def test_series_by_tag(fake: FakeUnreal) -> None:
    for name in ("CamZ", "CamY", "Other"):
        actor = fake.add_camera(name, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        if name != "Other":
            actor.tags.append("Portfolio")
    data = _load(mcp.capture_series(fake, "folio", tag="Portfolio"))
    assert data["cameras"] == ["CamY", "CamZ"]
    assert data["captures"][0]["camera"] == "CamY"


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({}, "invalid_series"),
        ({"cameras_json": '["A"]', "tag": "T"}, "invalid_series"),
        ({"tag": "Missing"}, "camera_not_found"),
        ({"tag": " "}, "invalid_series"),
        ({"cameras_json": '"A"'}, "invalid_json"),
        ({"cameras_json": '["A"]', "cursor": 3}, "invalid_series"),
    ],
)
def test_series_errors(fake: FakeUnreal, kwargs: dict[str, Any], code: str) -> None:
    fake.add_camera("A", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    data = _load(mcp.capture_series(fake, "tour", **kwargs))
    assert data["error"]["code"] == code
    assert fake.commands == []


def test_capture_bug_returns_markdown(fake: FakeUnreal, saved: Path) -> None:
    (saved / "Logs").mkdir()
    (saved / "Logs" / "Editor.log").write_text("LogTemp: Error: boom\n", encoding="utf-8")
    data = _load(mcp.capture_bug(fake, "Falls through floor", "high", "walk left"))
    assert data["error_count"] == 1
    assert data["markdown"].startswith("# Bug: Falls through floor")
    assert Path(data["report_path"]).is_file()
    assert data["status"] == "pending"
    bad = _load(mcp.capture_bug(fake, "t", "urgent"))
    assert bad["error"]["code"] == "invalid_severity"


def test_list_filters_and_contact_sheet(fake: FakeUnreal) -> None:
    ids = [
        _load(mcp.capture_viewport(fake, name))["capture_id"] for name in ("Hero", "tour", "hero2")
    ]
    listed = _load(mcp.list_captures(fake))
    assert [c["capture_id"] for c in listed["captures"]] == sorted(ids)  # path order
    heroes = _load(mcp.list_captures(fake, label="HERO"))
    assert sorted(c["label"] for c in heroes["captures"]) == ["Hero", "hero2"]
    assert _load(mcp.list_captures(fake, since="2000-01-01"))["captures"]
    assert _load(mcp.list_captures(fake, since="2999-01-01"))["captures"] == []
    assert len(_load(mcp.list_captures(fake, limit=1))["captures"]) == 1
    assert _load(mcp.list_captures(fake, since="yesterday"))["error"]["code"] == "invalid_filter"
    sheet = _load(mcp.build_contact_sheet_md(fake, json.dumps(ids[:2]), "Day 3"))
    assert sheet["count"] == 2
    assert sheet["content"].startswith("# Day 3")
    assert f"]({ids[0]})" in sheet["content"]
    missing = _load(mcp.build_contact_sheet_md(fake, '["Captures/nope.png"]'))
    assert missing["error"]["code"] == "unknown_capture"


def test_list_skips_bad_dates(fake: FakeUnreal) -> None:
    shot = _load(mcp.capture_viewport(fake, "odd"))
    sidecar = Path(shot["sidecar_path"])
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["captured_at"] = "not a date"
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    assert _load(mcp.list_captures(fake, since="2000-01-01"))["captures"] == []


def test_unexpected_failures_are_reported(fake: FakeUnreal, saved: Path) -> None:
    class Broken(FakeUnreal):
        def __getattribute__(self, name: str) -> Any:
            if name == "SystemLibrary":
                raise AttributeError("no SystemLibrary")
            return super().__getattribute__(name)

    broken = Broken()
    broken.saved_dir = str(saved)
    assert _load(mcp.capture_viewport(broken))["error"]["code"] == "unreal_error"
    (saved / "Captures").write_text("a file, not a folder", encoding="utf-8")
    assert _load(mcp.capture_viewport(fake))["error"]["code"] == "io_error"


def test_compat_resolves_subsystems(fake58: FakeUnreal58) -> None:
    assert compat.level_api(fake58) is fake58.subsystems[LevelEditorSubsystem]
    assert compat.editor_api(FakeUnreal()) is not None
    with compat.transaction(FakeUnreal(), "noop"):
        pass


def test_parse_json_rejects_huge_input(fake: FakeUnreal) -> None:
    data = _load(mcp.build_contact_sheet_md(fake, "x" * (mcp.MAX_JSON_CHARS + 1)))
    assert data["error"]["code"] == "invalid_json"


def test_to_json_handles_plain_values() -> None:
    assert json.loads(mcp.to_json({"a": (1, 2), "summary": "s", "p": object.__new__(object)}))[
        "a"
    ] == [1, 2]
    assert json.loads(mcp.to_json([1, None]))[1] is None

    @dataclass
    class Row:
        summary: str
        n: int

    assert mcp.to_json(Row("s", 1)) == '{"summary": "s", "n": 1}'
