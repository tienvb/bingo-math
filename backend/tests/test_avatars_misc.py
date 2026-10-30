"""Avatar manifest validation, network hints, static SPA serving."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.avatars import AvatarManifestError, load_avatars
from app.main import create_app
from app.network import is_private_lan_ipv4
from app.settings import BACKEND_DIR, Settings

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"></svg>'


def _entry(aid: str, image: str | None = None, **extra: object) -> dict[str, object]:
    return {"id": aid, "name": {"vi": aid, "en": aid}, "image": image or f"{aid}.svg",
            "win_animation": None, "color": "#123456", **extra}


def _write(tmp_path: Path, entries: object, files: list[str]) -> Path:
    for f in files:
        (tmp_path / f).write_text(SVG)
    (tmp_path / "manifest.json").write_text(json.dumps(entries))
    return tmp_path


def test_default_manifest_is_valid() -> None:
    avatars = load_avatars(BACKEND_DIR / "avatars")
    assert len(avatars) == 12
    assert len({a.id for a in avatars}) == 12
    for a in avatars:
        assert a.image_url.startswith("/avatars/") and a.color.startswith("#")
        assert a.name.vi and a.name.en
        assert (BACKEND_DIR / "avatars" / a.image_url.removeprefix("/avatars/")).is_file()


def test_manifest_ok(tmp_path: Path) -> None:
    (tmp_path / "dance.gif").write_bytes(b"GIF89a")
    d = _write(tmp_path, [_entry("a"), _entry("b", win_animation="dance.gif")], ["a.svg", "b.svg"])
    avatars = load_avatars(d)
    assert [a.id for a in avatars] == ["a", "b"]
    assert avatars[0].image_url == "/avatars/a.svg" and avatars[0].win_animation_url is None
    assert avatars[1].win_animation_url == "/avatars/dance.gif"


@pytest.mark.parametrize(
    "bad,files,needle",
    [
        (_entry("a"), [], "duplicate id"),  # second "a" skipped, first kept
        (_entry("b"), [], "not found"),
        (_entry("b", image="b.bmp"), ["b.bmp"], "must be one of"),
        (_entry("b", image="../x.svg"), [], "inside"),
        (_entry("b", win_animation="missing.gif"), ["b.svg"], "win_animation"),
        ({"id": "b"}, [], "name"),
    ],
)
def test_invalid_entries_are_skipped_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, bad: object, files: list[str], needle: str
) -> None:
    d = _write(tmp_path, [_entry("a"), bad, _entry("c")], ["a.svg", "c.svg", *files])
    with caplog.at_level(logging.WARNING, logger="bingo"):
        avatars = load_avatars(d)
    assert [a.id for a in avatars] == ["a", "c"]
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(needle in w and "[1]" in w for w in warnings), warnings


@pytest.mark.parametrize(
    "entries,files,needle",
    [
        ({"id": "a"}, [], "JSON array"),
        ([], [], "no valid avatar"),
        ([_entry("a")], [], "no valid avatar"),  # only entry has no image file
    ],
)
def test_manifest_fatal_errors(tmp_path: Path, entries: object, files: list[str], needle: str) -> None:
    d = _write(tmp_path, entries, files)
    with pytest.raises(AvatarManifestError, match=needle):
        load_avatars(d)


def test_app_starts_with_some_invalid_entries(tmp_path: Path) -> None:
    _write(tmp_path, [_entry("a"), _entry("ghost")], ["a.svg"])
    app = create_app(Settings(AVATARS_DIR=str(tmp_path)))
    with TestClient(app) as client:
        assert [a["id"] for a in client.get("/api/avatars").json()] == ["a"]


def test_manifest_missing_or_broken(tmp_path: Path) -> None:
    with pytest.raises(AvatarManifestError, match="not found"):
        load_avatars(tmp_path)
    (tmp_path / "manifest.json").write_text("{oops")
    with pytest.raises(AvatarManifestError, match="cannot read"):
        load_avatars(tmp_path)


@pytest.mark.parametrize("ip,ok", [("192.168.1.15", True), ("10.1.2.3", True), ("172.16.0.1", True),
                                   ("172.31.255.1", True), ("172.32.0.1", False), ("127.0.0.1", False),
                                   ("169.254.1.1", False), ("8.8.8.8", False), ("nope", False)])
def test_private_ip_filter(ip: str, ok: bool) -> None:
    assert is_private_lan_ipv4(ip) is ok


def test_static_spa_fallback(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    app = create_app(Settings(STATIC_DIR=str(tmp_path)))
    with TestClient(app) as client:
        for path in ("/", "/create", "/host/4729", "/screen/4729", "/play", "/play/4729"):
            r = client.get(path)
            assert r.status_code == 200 and "spa" in r.text, path
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert client.get("/api/health").json() == {"ok": True}
        assert client.get("/avatars/cat.svg").status_code == 200
