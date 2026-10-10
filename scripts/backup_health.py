#!/usr/bin/env python3
"""Copy workout originals into Health/Workouts.

Set HEALTH_BACKUP_DIR to the Health root. Insurance/ stays beside Workouts,
untouched.

Layout: Workouts/Garmin/fit/, Workouts/Xiaomi/{running,walking,...}/.
Also folds leftover files out of Runing/, Hiking/, Swimming/, and any
Garmin/ or Xiaomi/ that were previously next to Insurance/.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from jsonio import DATA
from xiaomi_sport import backup_folder

FIT_DIR = DATA / "workouts" / "fit"
TCX_DIR = DATA / "workouts" / "tcx"
GPX_DIR = DATA / "workouts" / "gpx"
XIAOMI_KINDS = (
    "running",
    "walking",
    "hiking",
    "cycling",
    "swimming",
    "training",
    "archives",
)


def health_root() -> Path:
    raw = os.environ.get("HEALTH_BACKUP_DIR", "").strip()
    if not raw:
        raise SystemExit("HEALTH_BACKUP_DIR unset")
    return Path(raw)


def workouts_root(health: Path) -> Path:
    return health / "Workouts"


def copy_file(src: Path, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == src.stat().st_size:
        return "skip"
    shutil.copy2(src, dest)
    return "copy"


def move_file(src: Path, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.resolve() == src.resolve():
        return "skip"
    if dest.exists():
        src.unlink()
        return "dedupe"
    shutil.move(str(src), str(dest))
    return "move"


def _rmdir_empty(folder: Path) -> None:
    if not folder.is_dir():
        return
    for child in sorted(folder.rglob("*"), reverse=True):
        if child.is_dir():
            try:
                child.rmdir()
            except OSError:
                pass
    try:
        folder.rmdir()
    except OSError:
        pass


def reorganize(health: Path) -> dict[str, int]:
    counts = {"move": 0, "dedupe": 0, "skip": 0}
    workouts = workouts_root(health)
    xiaomi = workouts / "Xiaomi"
    garmin = workouts / "Garmin" / "fit"
    leftovers = []
    for name in ("Runing", "Hiking", "Swimming"):
        folder = health / name
        if folder.is_dir():
            leftovers.extend(p for p in folder.rglob("*") if p.is_file())
    old_xiaomi = health / "Xiaomi"
    if old_xiaomi.is_dir():
        leftovers.extend(p for p in old_xiaomi.rglob("*") if p.is_file())
    old_garmin = health / "Garmin"
    if old_garmin.is_dir():
        leftovers.extend(p for p in old_garmin.rglob("*") if p.is_file())
    for path in leftovers:
        suffix = path.suffix.lower()
        if suffix == ".fit":
            dest = garmin / path.name
        elif suffix in {".tcx", ".gpx"}:
            dest = xiaomi / backup_folder(path) / path.name
        else:
            dest = xiaomi / "archives" / path.name
        counts[move_file(path, dest)] += 1
    for name in ("Runing", "Hiking", "Swimming", "Xiaomi", "Garmin"):
        _rmdir_empty(health / name)
    return counts


def sync_repo(health: Path) -> dict[str, int]:
    counts = {"copy": 0, "skip": 0}
    workouts = workouts_root(health)
    garmin = workouts / "Garmin" / "fit"
    xiaomi = workouts / "Xiaomi"
    for kind in XIAOMI_KINDS:
        (xiaomi / kind).mkdir(parents=True, exist_ok=True)
    garmin.mkdir(parents=True, exist_ok=True)
    if FIT_DIR.is_dir():
        for src in sorted(FIT_DIR.glob("*.fit")):
            counts[copy_file(src, garmin / src.name)] += 1
    if TCX_DIR.is_dir():
        for src in sorted(TCX_DIR.glob("*.tcx")):
            dest = xiaomi / backup_folder(src) / src.name
            counts[copy_file(src, dest)] += 1
    if GPX_DIR.is_dir():
        for src in sorted(GPX_DIR.glob("*.gpx")):
            dest = xiaomi / backup_folder(src) / src.name
            counts[copy_file(src, dest)] += 1
    return counts


def main() -> None:
    health = health_root()
    if not health.is_dir():
        raise SystemExit(f"Health folder not found: {health}")
    moved = reorganize(health)
    synced = sync_repo(health)
    print("reorganize move {move} dedupe {dedupe} skip {skip}".format(**moved))
    print("sync copy {copy} skip {skip}".format(**synced))
    print(f"health {health}")
    print(f"workouts {workouts_root(health)}")


if __name__ == "__main__":
    main()
