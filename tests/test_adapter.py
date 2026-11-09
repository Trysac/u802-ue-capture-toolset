from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fakes.unreal import FakeUnreal, FakeUnreal58, Vector

from ue_capture_toolset import (
    CaptureError,
    cameras_with_tag,
    capture_bug,
    capture_pair,
    capture_series,
    capture_viewport,
    list_captures,
    poll_capture,
)
from ue_capture_toolset.core.sidecar import load_sidecar

SHA = "0123456789abcdef0123456789abcdef01234567"
AT = datetime(2026, 11, 8, 9, 5, 7)


def test_capture_viewport_requests_shot_and_writes_sidecar(
    ue: FakeUnreal, saved: Path, tmp_path: Path
) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text(SHA + "\n", encoding="utf-8")
    capture = capture_viewport(
        ue, saved, label="hero shot", resolution="1920x1080", at=AT, clock=lambda: 10.0
    )
    assert capture.status == "pending"
    assert capture.image_path.endswith("090507-hero-shot.png")
    assert capture.requested_at == 10.0
    assert len(ue.commands) == 1
    assert ue.commands[0].startswith("HighResShot 1920x1080 filename=")
    sidecar = load_sidecar(capture.sidecar_path)
    assert sidecar.git_commit == SHA
    assert sidecar.image == "Captures/2026-11-08/090507-hero-shot.png"
    assert sidecar.map == "/Game/Maps/Arena.Arena"
    assert len(sidecar.quality) == 10
    assert sidecar.location == (1234.5678, -42.125, 88.0)
    assert sidecar.rotation == (-10.5, 135.25, 0.0)


def test_viewport_without_status_value(ue: FakeUnreal, saved: Path) -> None:
    ue.viewport_with_status = False
    capture = capture_viewport(ue, saved, at=AT)
    assert capture.camera == "viewport"


def test_viewport_reads_provenance(ue: FakeUnreal, saved: Path) -> None:
    (saved / "provenance.json").write_text('[{"tool": "gen"}]', encoding="utf-8")
    capture = capture_viewport(ue, saved, at=AT)
    assert load_sidecar(capture.sidecar_path).provenance == ({"tool": "gen"},)


def test_invalid_inputs_do_not_touch_unreal(ue: FakeUnreal, saved: Path, tmp_path: Path) -> None:
    with pytest.raises(CaptureError) as info:
        capture_viewport(ue, saved, resolution="0x5")
    assert info.value.code == "invalid_resolution"
    with pytest.raises(CaptureError) as info2:
        capture_viewport(ue, tmp_path / 'we"ird', at=AT)
    assert info2.value.code == "invalid_path"
    assert ue.commands == []


def test_poll_capture(ue: FakeUnreal, saved: Path) -> None:
    capture = capture_viewport(ue, saved, at=AT, clock=lambda: 10.0, timeout_s=30.0)
    assert poll_capture(capture, clock=lambda: 20.0) is capture
    with pytest.raises(CaptureError) as info:
        poll_capture(capture, clock=lambda: 100.0)
    assert info.value.code == "capture_timeout"
    Path(capture.image_path).write_bytes(b"")
    assert poll_capture(capture, clock=lambda: 20.0).status == "pending"
    Path(capture.image_path).write_bytes(b"png")
    ready = poll_capture(capture, clock=lambda: 20.0)
    assert ready.status == "ready"
    assert ready.summary.startswith("Capture ready")


def test_poll_default_clock_with_auto_write(saved: Path) -> None:
    fake = FakeUnreal(auto_write=True)
    capture = capture_viewport(fake, saved, at=AT)
    assert poll_capture(capture).status == "ready"


def test_capture_pair_copies_transform(ue: FakeUnreal, saved: Path) -> None:
    before = capture_viewport(ue, saved, label="before", resolution="1280x720", at=AT)
    prior = load_sidecar(before.sidecar_path)
    result = capture_pair(
        ue, saved, before.sidecar_path, label="after", at=AT + timedelta(seconds=5)
    )
    cameras = [a for a in ue.actors if a.cls is ue.CameraActor]
    assert len(cameras) == 1
    new = cameras[0]
    location = (new.get_actor_location().x, new.get_actor_location().y, new.get_actor_location().z)
    rotation = (
        new.get_actor_rotation().pitch,
        new.get_actor_rotation().yaw,
        new.get_actor_rotation().roll,
    )
    for got, want in zip(location + rotation, prior.location + prior.rotation, strict=True):
        assert abs(got - want) < 1e-3
    assert ue.piloted == [new]
    assert new.get_actor_label() == "Pair_after"
    assert result.camera == "Pair_after"
    assert result.before == prior
    assert result.after.resolution == (1280, 720)
    assert load_sidecar(result.after.sidecar_path).camera == "Pair_after"
    assert "after" in result.summary


def test_capture_pair_accepts_image_and_relative_paths(ue: FakeUnreal, saved: Path) -> None:
    before = capture_viewport(ue, saved, label="b", at=AT)
    by_image = capture_pair(ue, saved, before.image_path, resolution="640x480", at=AT)
    assert by_image.after.resolution == (640, 480)
    relative = capture_pair(ue, saved, "Captures/2026-11-08/090507-b.png", at=AT)
    assert relative.before.label == "b"


def test_capture_pair_unknown_before(ue: FakeUnreal, saved: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    for ref in (outside, "Captures/missing.png", "notes.txt", "../outside.json"):
        with pytest.raises(CaptureError) as info:
            capture_pair(ue, saved, ref)
        assert info.value.code == "unknown_capture"
    assert ue.actors == []


def test_capture_pair_bad_resolution_spawns_nothing(ue: FakeUnreal, saved: Path) -> None:
    before = capture_viewport(ue, saved, at=AT)
    with pytest.raises(CaptureError):
        capture_pair(ue, saved, before.sidecar_path, resolution="0x5")
    assert ue.actors == []


def test_capture_series(ue: FakeUnreal, saved: Path) -> None:
    ue.add_camera("CamA", (1.0, 2.0, 3.0), (0.0, 90.0, 0.0))
    ue.add_camera("CamB", (4.0, 5.0, 6.0), (10.0, 20.0, 30.0))
    result = capture_series(ue, saved, "tour", ["CamA", "CamB"], at=AT)
    assert len(result.captures) == 2
    assert len(ue.commands) == 2
    assert [a.get_actor_label() for a in ue.piloted] == ["CamA", "CamB"]
    second = load_sidecar(result.captures[1].sidecar_path)
    assert second.camera == "CamB"
    assert second.location == (4.0, 5.0, 6.0)
    assert second.rotation == (10.0, 20.0, 30.0)
    assert "2 captures" in result.summary


def test_capture_series_errors(ue: FakeUnreal, saved: Path) -> None:
    ue.add_camera("CamA", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    with pytest.raises(CaptureError) as info:
        capture_series(ue, saved, "tour", ["CamA", "Nope"])
    assert info.value.code == "camera_not_found"
    assert ue.commands == []
    for bad in ([], "CamA", ["CamA"] * 51):
        with pytest.raises(CaptureError) as info2:
            capture_series(ue, saved, "tour", bad)
        assert info2.value.code == "invalid_series"
    with pytest.raises(CaptureError):
        capture_series(ue, saved, "tour", ["CamA"], resolution="bad")


def test_capture_bug_with_log(ue: FakeUnreal, saved: Path) -> None:
    logs = saved / "Logs"
    logs.mkdir()
    (logs / "Editor.log").write_text(
        "LogTemp: Error: one\nLogTemp: Warning: w\nLogTemp: Error: two\n", encoding="utf-8"
    )
    result = capture_bug(ue, saved, "Crash on load", "high", notes="steps", at=AT)
    report = Path(result.report_path).read_text(encoding="utf-8")
    assert result.error_count == 2
    assert "# Bug: Crash on load" in report
    assert "- `LogTemp: Error: one`" in report
    assert f"({Path(result.capture.image_path).name})" in report
    assert "> steps" in report
    assert result.report_path.endswith(".md")
    assert "high" in result.summary
    again = capture_bug(ue, saved, "Again", at=AT, log_path="Logs/Editor.log")
    assert again.error_count == 2
    assert again.report_path != result.report_path


def test_capture_bug_without_logs(ue: FakeUnreal, saved: Path) -> None:
    result = capture_bug(ue, saved, "No log", at=AT)
    assert result.error_count == 0
    assert "## Recent errors\n\n- none recorded" in Path(result.report_path).read_text("utf-8")


def test_capture_bug_validation(ue: FakeUnreal, saved: Path, tmp_path: Path) -> None:
    with pytest.raises(CaptureError) as info:
        capture_bug(ue, saved, "t", "urgent")
    assert info.value.code == "invalid_severity"
    outside = tmp_path / "outside.log"
    outside.write_text("Error: x", encoding="utf-8")
    with pytest.raises(CaptureError) as info2:
        capture_bug(ue, saved, "t", "low", log_path=outside)
    assert info2.value.code == "invalid_path"
    assert ue.commands == []


def test_list_captures(ue: FakeUnreal, saved: Path) -> None:
    empty = list_captures(ue, saved)
    assert empty.captures == ()
    for offset in range(3):
        capture_viewport(ue, saved, label=f"s{offset}", at=AT + timedelta(seconds=offset))
    folder = saved / "Captures" / "2026-11-08"
    (folder / "000000-broken.json").write_text("not json", encoding="utf-8")
    listed = list_captures(ue, saved)
    assert [s.label for s in listed.captures] == ["s0", "s1", "s2"]
    assert listed.skipped == 1
    assert "3 captures" in listed.summary
    newest = list_captures(ue, saved, limit=2)
    assert [s.label for s in newest.captures] == ["s1", "s2"]
    assert newest.skipped == 0
    assert len(list_captures(ue, saved, limit=0).captures) == 1


def test_series_cursor_and_limit(ue: FakeUnreal, saved: Path) -> None:
    for name in ("A", "B", "C"):
        ue.add_camera(name, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    first = capture_series(ue, saved, "t", ["A", "B", "C"], limit=2, at=AT)
    assert first.cursor == 2 and len(first.captures) == 2
    rest = capture_series(ue, saved, "t", ["A", "B", "C"], cursor=2, at=AT)
    assert rest.cursor is None and rest.captures[0].camera == "C"
    for kwargs in ({"cursor": 3}, {"cursor": -1}, {"limit": 0}):
        with pytest.raises(CaptureError) as info:
            capture_series(ue, saved, "t", ["A"], **kwargs)
        assert info.value.code == "invalid_series"


def test_cameras_with_tag(ue: FakeUnreal) -> None:
    ue.add_camera("B", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)).tags.append("Folio")
    ue.add_camera("A", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)).tags.append("Folio")
    assert cameras_with_tag(ue, "Folio") == ("A", "B")
    with pytest.raises(CaptureError) as info:
        cameras_with_tag(ue, "None")
    assert info.value.code == "camera_not_found"


def test_viewport_from_camera_works_on_ue58(saved: Path) -> None:
    ue = FakeUnreal58()
    ue.add_camera("Cam", (1.0, 2.0, 3.0), (4.0, 5.0, 6.0))
    capture = capture_viewport(ue, saved, camera="Cam", at=AT)
    sidecar = load_sidecar(capture.sidecar_path)
    assert sidecar.camera == "Cam" and sidecar.location == (1.0, 2.0, 3.0)
    assert ue.piloted[0].get_actor_label() == "Cam"
    assert not hasattr(ue, "EditorLevelLibrary")


def test_pair_on_ue58_reproduces_transform_via_viewport(saved: Path) -> None:
    ue = FakeUnreal58()
    before = capture_viewport(ue, saved, label="before", at=AT)
    prior = load_sidecar(before.sidecar_path)
    ue.viewport_location = Vector(0.0, 0.0, 0.0)
    result = capture_pair(ue, saved, before.sidecar_path, at=AT + timedelta(seconds=1))
    after = load_sidecar(result.after.sidecar_path)
    for got, want in zip(
        after.location + after.rotation, prior.location + prior.rotation, strict=True
    ):
        assert abs(got - want) < 1e-3
    moved_location, moved_rotation = ue.viewport_moves[0]
    assert (moved_location.x, moved_rotation.yaw) == (prior.location[0], prior.rotation[1])
    assert ue.actors == [] and result.camera == "viewport"
