"""Read and validate `avatars/manifest.json` (*Nhân vật và animation chiến thắng*)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.schemas import Avatar, AvatarManifestEntry

log = logging.getLogger("bingo")

MANIFEST_NAME = "manifest.json"
IMAGE_SUFFIXES = {".png", ".webp", ".svg"}
ANIMATION_SUFFIXES = {".gif", ".webp", ".json"}
URL_PREFIX = "/avatars"


class AvatarManifestError(RuntimeError):
    """Startup failure: manifest unreadable / not valid JSON, or no valid avatar at all.

    Invalid entries are skipped with a warning naming each problem."""


def _check_file(base: Path, name: str, allowed: set[str], what: str) -> str | None:
    path = (base / name).resolve()
    if base.resolve() not in path.parents:
        return f"{what} {name!r} must be a file inside {base}"
    if path.suffix.lower() not in allowed:
        return f"{what} {name!r} must be one of {sorted(allowed)}"
    if not path.is_file():
        return f"{what} file {name!r} not found in {base}"
    return None


def load_avatars(avatars_dir: Path) -> list[Avatar]:
    manifest = avatars_dir / MANIFEST_NAME
    if not manifest.is_file():
        raise AvatarManifestError(f"avatar manifest not found: {manifest}")
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AvatarManifestError(f"cannot read {manifest}: {exc}") from exc
    if not isinstance(raw, list):
        raise AvatarManifestError(f"{manifest}: top level must be a JSON array of avatars")

    avatars: list[Avatar] = []
    seen: set[str] = set()
    skipped = 0
    for i, item in enumerate(raw):
        where = f"{manifest.name}[{i}]"
        problems: list[str] = []
        try:
            entry = AvatarManifestEntry.model_validate(item)
        except ValidationError as exc:
            details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            log.warning("avatar skipped, %s: %s", where, details)
            skipped += 1
            continue
        where = f"{where} (id={entry.id!r})"
        if not entry.id.strip():
            problems.append("id must not be empty")
        elif entry.id in seen:
            problems.append("duplicate id (the first entry with this id is kept)")
        err = _check_file(avatars_dir, entry.image, IMAGE_SUFFIXES, "image")
        if err:
            problems.append(err)
        if entry.win_animation:
            err = _check_file(avatars_dir, entry.win_animation, ANIMATION_SUFFIXES, "win_animation")
            if err:
                problems.append(err)
        if problems:
            for problem in problems:
                log.warning("avatar skipped, %s: %s", where, problem)
            skipped += 1
            continue
        seen.add(entry.id)
        avatars.append(
            Avatar(
                id=entry.id,
                name=entry.name,
                image_url=f"{URL_PREFIX}/{entry.image}",
                win_animation_url=f"{URL_PREFIX}/{entry.win_animation}" if entry.win_animation else None,
                color=entry.color,
            )
        )
    if not avatars:
        raise AvatarManifestError(
            f"{manifest}: no valid avatar ({skipped} invalid entries, see warnings above)"
        )
    if skipped:
        log.warning("%d invalid avatar entries skipped in %s", skipped, manifest)
    log.info("loaded %d avatars from %s", len(avatars), avatars_dir)
    return avatars
