import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ue_capture_toolset import (
    CaptureError,
    Sidecar,
    build_bug_markdown,
    build_contact_sheet_md,
    capture_path,
    parse_resolution,
    read_git_commit,
    recent_errors,
)
from ue_capture_toolset.core import gitinfo, logscan
from ue_capture_toolset.core import paths as paths_module
from ue_capture_toolset.core import sidecar as sidecar_module
from ue_capture_toolset.core.logscan import read_log_tail
from ue_capture_toolset.core.markdown import normalize_severity
from ue_capture_toolset.core.paths import slugify
from ue_capture_toolset.core.sidecar import (
    load_sidecar,
    read_provenance,
    sidecar_path_for,
    write_sidecar,
)

HERE = Path(__file__).parent
SHA = "0123456789abcdef0123456789abcdef01234567"
SHA2 = "fedcba9876543210fedcba9876543210fedcba98"


def make_sidecar(**changes: Any) -> Sidecar:
    base = Sidecar(
        image="Captures/2026-11-08/090507-alpha.png",
        label="alpha",
        map="/Game/Maps/Arena",
        camera="CamA",
        location=(1.0, 2.0, 3.0),
        rotation=(0.0, 90.0, 0.0),
        resolution=(1920, 1080),
        quality={"sg.ShadowQuality": 3},
        git_commit="abcdef0123456789abcdef0123456789abcdef01",
        captured_at="2026-11-08T09:05:07",
    )
    return replace(base, **changes)


# resolution


def test_parse_resolution_ok() -> None:
    assert parse_resolution("1920x1080") == (1920, 1080)
    assert parse_resolution(" 640X480 ") == (640, 480)


@pytest.mark.parametrize(
    "text",
    [
        "0x5",
        "5x0",
        "1920",
        "1920x",
        "x1080",
        "-1x5",
        "1920x1080x2",
        "20000x5",
        "99999x1",
        "",
        "1x1" + " " * 40,
    ],
)
def test_parse_resolution_rejects(text: str) -> None:
    if text == "1x1" + " " * 40 or text != "1x1":
        with pytest.raises(CaptureError) as info:
            parse_resolution(text)
        assert info.value.code == "invalid_resolution"


def test_parse_resolution_rejects_non_text_and_unicode_digits() -> None:
    with pytest.raises(CaptureError):
        parse_resolution(5)  # type: ignore[arg-type]
    with pytest.raises(CaptureError):
        parse_resolution(chr(0x661) + chr(0x662) + "x" + chr(0x663))


@given(st.integers(1, 16384), st.integers(1, 16384))
@settings(derandomize=True, max_examples=50, deadline=None)
def test_parse_resolution_roundtrip(w: int, h: int) -> None:
    assert parse_resolution(f"{w}x{h}") == (w, h)


# paths


def test_capture_path_format(tmp_path: Path) -> None:
    result = capture_path(tmp_path, label="hero shot", at=datetime(2026, 11, 8, 9, 5, 7))
    assert result == tmp_path / "Captures" / "2026-11-08" / "090507-hero-shot.png"


def test_capture_path_default_time(tmp_path: Path) -> None:
    assert capture_path(tmp_path).name.endswith("-capture.png")


def test_same_label_same_second_is_unique_and_sorts_after_earlier(tmp_path: Path) -> None:
    moment = datetime(2026, 11, 8, 9, 5, 7)
    earlier = capture_path(tmp_path, label="a", at=moment - timedelta(seconds=1))
    first = capture_path(tmp_path, label="a", at=moment)
    second = capture_path(tmp_path, label="a", at=moment)
    assert first != second
    assert str(first) > str(earlier)
    assert str(second) > str(earlier)
    assert str(second) > str(first)


def test_existing_file_gets_suffix(tmp_path: Path) -> None:
    moment = datetime(2026, 1, 2, 3, 4, 5)
    folder = tmp_path / "Captures" / "2026-01-02"
    folder.mkdir(parents=True)
    (folder / "030405-x.png").write_bytes(b"")
    assert capture_path(tmp_path, "x", moment).name == "030405-x~002.png"


def test_collision_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths_module, "MAX_COLLISIONS", 1)
    moment = datetime(2026, 1, 2, 3, 4, 5)
    capture_path(tmp_path, "x", moment)
    with pytest.raises(CaptureError) as info:
        capture_path(tmp_path, "x", moment)
    assert info.value.code == "too_many_captures"


def test_reservations_are_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paths_module, "MAX_RESERVED", 2)
    for second in range(5):
        capture_path(tmp_path, "x", datetime(2026, 1, 2, 3, 4, second))
    assert len(paths_module._reserved) == 2


def test_slugify() -> None:
    assert slugify("hero shot") == "hero-shot"
    assert slugify("  Ünï Côdé!! ") == "uni-code"
    assert slugify("") == "capture"
    assert slugify("***") == "capture"
    assert slugify("../../etc/passwd") == "etc-passwd"
    assert slugify("a" * 100) == "a" * 40
    assert slugify("a" * 39 + " b") == "a" * 39


def test_slugify_rejects_long_label() -> None:
    with pytest.raises(CaptureError) as info:
        slugify("x" * 201)
    assert info.value.code == "invalid_label"


_counter = iter(range(10**9))


@given(
    st.lists(
        st.tuples(st.integers(0, 200000), st.sampled_from(["a", "b", "hero shot"])),
        min_size=1,
        max_size=10,
    )
)
@settings(derandomize=True, max_examples=50, deadline=None)
def test_paths_unique_and_time_sortable(items: list[tuple[int, str]]) -> None:
    saved = Path("virtual-saved") / str(next(_counter))
    base = datetime(2026, 1, 1)
    made = [(s, capture_path(saved, label, base + timedelta(seconds=s))) for s, label in items]
    assert len({p for _, p in made}) == len(made)
    for s1, p1 in made:
        for s2, p2 in made:
            if s1 < s2:
                assert str(p1) < str(p2)


@given(st.text(max_size=200))
@settings(derandomize=True, max_examples=50, deadline=None)
def test_slug_charset(label: str) -> None:
    slug = slugify(label)
    assert 1 <= len(slug) <= 40
    assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in slug)


# sidecar


def test_sidecar_roundtrip(tmp_path: Path) -> None:
    original = make_sidecar(provenance=({"tool": "gen"},))
    path = sidecar_path_for(tmp_path / "x" / "a.png")
    write_sidecar(path, original)
    assert path.name == "a.json"
    assert load_sidecar(path) == original
    assert "alpha on /Game/Maps/Arena" in original.summary


@pytest.mark.parametrize(
    "change",
    [
        {"image": 5},
        {"image": "x" * 501},
        {"location": [1, 2]},
        {"location": [1, 2, float("nan")]},
        {"location": [1, 2, True]},
        {"location": "abc"},
        {"resolution": [0, 5]},
        {"resolution": [1920]},
        {"resolution": [1.5, 2]},
        {"quality": {"sg.X": "3"}},
        {"quality": []},
        {"quality": {f"k{i}": 1 for i in range(65)}},
        {"provenance": [1]},
        {"provenance": "x"},
        {"git_commit": 5},
    ],
)
def test_sidecar_rejects_bad_fields(change: dict[str, Any]) -> None:
    data = make_sidecar().to_dict()
    data.update(change)
    with pytest.raises(CaptureError) as info:
        Sidecar.from_dict(data)
    assert info.value.code == "invalid_sidecar"


def test_sidecar_rejects_non_object() -> None:
    with pytest.raises(CaptureError):
        Sidecar.from_dict([1])


def test_load_sidecar_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(CaptureError) as info:
        load_sidecar(tmp_path / "missing.json")
    assert info.value.code == "unknown_capture"
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(CaptureError) as info2:
        load_sidecar(bad)
    assert info2.value.code == "invalid_sidecar"
    good = tmp_path / "good.json"
    write_sidecar(good, make_sidecar())
    monkeypatch.setattr(sidecar_module, "MAX_SIDECAR_BYTES", 10)
    with pytest.raises(CaptureError) as info3:
        load_sidecar(good)
    assert info3.value.code == "invalid_sidecar"


def test_read_provenance_formats(tmp_path: Path) -> None:
    path = tmp_path / "provenance.json"
    assert read_provenance(path) == ()
    path.write_text(json.dumps([{"a": 1}]), encoding="utf-8")
    assert read_provenance(path) == ({"a": 1},)
    path.write_text(json.dumps({"entries": [{"b": 2}]}), encoding="utf-8")
    assert read_provenance(path) == ({"b": 2},)
    path.write_text(json.dumps({"provenance": [{"c": 3}]}), encoding="utf-8")
    assert read_provenance(path) == ({"c": 3},)
    path.write_text(json.dumps([{"n": i} for i in range(150)]), encoding="utf-8")
    kept = read_provenance(path)
    assert len(kept) == 100
    assert kept[-1] == {"n": 149}


@pytest.mark.parametrize("text", ["nope", "5", "[1]", '{"other": []}'])
def test_read_provenance_rejects(tmp_path: Path, text: str) -> None:
    path = tmp_path / "provenance.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(CaptureError):
        read_provenance(path)


# git


def make_repo(
    root: Path,
    head: str,
    refs: dict[str, str] | None = None,
    packed: dict[str, str] | None = None,
) -> None:
    git = root / ".git"
    git.mkdir(parents=True)
    (git / "HEAD").write_text(head + "\n", encoding="utf-8")
    for ref, sha in (refs or {}).items():
        target = git / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(sha + "\n", encoding="utf-8")
    if packed is not None:
        body = "# pack-refs with: peeled fully-peeled sorted\ngarbage\n"
        body += f"{SHA2} refs/heads/other\n^{SHA2}\n"
        body += "".join(f"{sha} {ref}\n" for ref, sha in packed.items())
        (git / "packed-refs").write_text(body, encoding="utf-8")


def test_git_loose_ref(tmp_path: Path) -> None:
    make_repo(tmp_path, "ref: refs/heads/main", refs={"refs/heads/main": SHA})
    result = read_git_commit(tmp_path)
    assert result == SHA
    assert len(result) == 40


def test_git_packed_ref_only(tmp_path: Path) -> None:
    make_repo(tmp_path, "ref: refs/heads/main", packed={"refs/heads/main": SHA})
    result = read_git_commit(tmp_path)
    assert result == SHA
    assert len(result) == 40


def test_git_detached_and_missing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    make_repo(repo, SHA.upper())
    assert read_git_commit(repo) == SHA
    bare = tmp_path / "plain"
    bare.mkdir()
    assert read_git_commit(bare) is None


@pytest.mark.parametrize(
    "head",
    [
        "ref: refs/heads/../../x",
        "ref: heads/main",
        "ref: refs/heads/",
        "garbage",
        "ref: refs/heads/none",
    ],
)
def test_git_unusable_heads(tmp_path: Path, head: str) -> None:
    make_repo(tmp_path, head, packed={})
    assert read_git_commit(tmp_path) is None


def test_git_empty_and_huge_head(tmp_path: Path) -> None:
    make_repo(tmp_path, "")
    assert read_git_commit(tmp_path) is None
    (tmp_path / ".git" / "HEAD").write_text("x" * 70000, encoding="utf-8")
    assert read_git_commit(tmp_path) is None


def test_git_packed_too_large(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_repo(tmp_path, "ref: refs/heads/main", packed={"refs/heads/main": SHA})
    monkeypatch.setattr(gitinfo, "MAX_PACKED_BYTES", 10)
    assert read_git_commit(tmp_path) is None


def test_git_worktrees(tmp_path: Path) -> None:
    main = tmp_path / "main"
    make_repo(main, "ref: refs/heads/dev", refs={"refs/heads/feat": SHA})
    wt_git = main / ".git" / "worktrees" / "wt"
    wt_git.mkdir(parents=True)
    (wt_git / "HEAD").write_text("ref: refs/heads/feat\n", encoding="utf-8")
    (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
    absolute = tmp_path / "wt"
    absolute.mkdir()
    (absolute / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
    assert read_git_commit(absolute) == SHA
    relative = tmp_path / "wt2"
    relative.mkdir()
    (relative / ".git").write_text("gitdir: ../main/.git/worktrees/wt\n", encoding="utf-8")
    assert read_git_commit(relative) == SHA
    (wt_git / "commondir").write_text(".\n", encoding="utf-8")
    assert read_git_commit(absolute) is None


def test_git_file_without_valid_gitdir(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("nonsense", encoding="utf-8")
    assert read_git_commit(tmp_path) is None
    (tmp_path / ".git").write_text("gitdir: nowhere", encoding="utf-8")
    assert read_git_commit(tmp_path) is None


# logs


def test_recent_errors_last_twenty_in_order() -> None:
    lines = []
    for i in range(30):
        lines.append(f"LogTemp: Error: problem {i}")
        lines.append("LogTemp: Warning: noise")
    result = recent_errors("\n".join(lines))
    assert result == [f"LogTemp: Error: problem {i}" for i in range(10, 30)]


def test_recent_errors_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    assert recent_errors("Error: a\r\nError: b\r\n", limit=1) == ["Error: b"]
    assert recent_errors("Error: a", limit=0) == []
    assert recent_errors("NoError: x\nerror: y\nLogX: Error:tight") == ["LogX: Error:tight"]
    assert len(recent_errors("Error: " + "x" * 1000)[0]) == 500
    monkeypatch.setattr(logscan, "MAX_LOG_CHARS", 10)
    with pytest.raises(CaptureError) as info:
        recent_errors("x" * 11)
    assert info.value.code == "input_too_large"


@given(st.integers(0, 60))
@settings(derandomize=True, max_examples=30, deadline=None)
def test_recent_errors_property(count: int) -> None:
    expected = [f"LogA: Error: {i}" for i in range(count)]
    assert recent_errors("\n".join(expected)) == expected[-20:]


def test_read_log_tail(tmp_path: Path) -> None:
    log = tmp_path / "a.log"
    log.write_bytes(b"a" * 50 + b"\nLogTemp: Error: tail\xff")
    assert read_log_tail(log, max_bytes=30).endswith("Error: tail\ufffd")
    assert read_log_tail(log).startswith("aaaa")
    assert read_log_tail(tmp_path / "missing.log") == ""
    assert read_log_tail(tmp_path) == ""


# markdown


def test_bug_markdown_matches_golden() -> None:
    sidecar = load_sidecar(HERE / "fixtures" / "bug_sidecar.json")
    errors = ["LogTemp: Error: Floor collision missing", "LogPhysics: Error: Body 12 has no shape"]
    text = build_bug_markdown(
        sidecar,
        severity="high",
        title="Player falls through floor",
        notes="Happens after jumping twice.\nSecond line.",
        errors=errors,
    )
    assert text == (HERE / "golden" / "bug.md").read_text(encoding="utf-8")


def test_bug_markdown_variants() -> None:
    plain = make_sidecar(quality={}, git_commit=None, provenance=({"tool": "gen", "id": 1},))
    text = build_bug_markdown(plain, severity=" HIGH ", title="x\ny `z` [w]", notes="a\n\nb")
    assert "# Bug: x y 'z' [w]" in text
    assert "![x y 'z' (w)](" in text
    assert "- **Severity:** high" in text
    assert "- **Commit:** unknown" in text
    assert "## Quality preset\n\n- none recorded" in text
    assert "## Recent errors\n\n- none recorded" in text
    assert '- {"id": 1, "tool": "gen"}' in text
    assert "> a\n>\n> b\n" in text
    spaced = make_sidecar(image="Captures/a b.png")
    assert "(Captures/a%20b.png)" in build_bug_markdown(spaced, severity="low", title="t")
    assert "(custom.png)" in build_bug_markdown(
        spaced, severity="low", title="t", image_link="custom.png"
    )


def test_bug_markdown_caps_errors_and_validates() -> None:
    many = [f"Err {i}" for i in range(25)]
    text = build_bug_markdown(make_sidecar(), severity="low", title="t", errors=many)
    assert text.count("- `Err ") == 20
    assert "`Err 24`" in text
    assert "`Err 4`" not in text
    with pytest.raises(CaptureError) as info:
        build_bug_markdown(make_sidecar(), severity="urgent", title="t")
    assert info.value.code == "invalid_severity"
    with pytest.raises(CaptureError) as info2:
        build_bug_markdown(make_sidecar(), severity="low", title="t", notes="n" * 20001)
    assert info2.value.code == "input_too_large"
    assert normalize_severity("Critical") == "critical"


def test_contact_sheet_matches_golden_without_reading_images(tmp_path: Path) -> None:
    sheets = [
        make_sidecar(),
        make_sidecar(
            label="beta",
            image="Captures/2026-11-08/090612-beta.png",
            camera="CamB",
            captured_at="2026-11-08T09:06:12",
            git_commit=None,
        ),
        make_sidecar(
            label="gamma shot",
            image="Captures/2026-11-09/101500-gamma-shot.png",
            map="/Game/Maps/Vault",
            camera="CamC",
            captured_at="2026-11-09T10:15:00",
            git_commit="1234567890abcdef1234567890abcdef12345678",
        ),
    ]
    text = build_contact_sheet_md(sheets)
    assert text == (HERE / "golden" / "contact_sheet.md").read_text(encoding="utf-8")
    assert text.count("![") == 3
    assert not (tmp_path / "Captures").exists()


def test_contact_sheet_edges() -> None:
    assert "1 capture." in build_contact_sheet_md([make_sidecar()], title="My `sheet`")
    assert build_contact_sheet_md([]).endswith("0 captures.\n")
    with pytest.raises(CaptureError) as info:
        build_contact_sheet_md([make_sidecar()] * 201)
    assert info.value.code == "too_many_captures"


def test_error_message_is_bounded() -> None:
    error = CaptureError("x", "m" * 500)
    assert len(error.message) == 200
    assert error.code == "x"
