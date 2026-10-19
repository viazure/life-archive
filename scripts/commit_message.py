#!/usr/bin/env python3
"""Build a commit subject from staged archive deltas.

Git already stores dates and file lists. This only reports item-count
changes that you cannot see from `git log` alone.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]


def resolve_data_root() -> Path:
    env = os.environ.get("LIFE_DATA_ROOT", "").strip()
    return Path(env).expanduser().resolve() if env else CODE_ROOT.resolve()


ROOT = resolve_data_root()

FETCH_LISTS = (
    (Path("data/lastfm/scrobbles.json"), "听歌"),
    (Path("data/lastfm/loved.json"), "红心"),
    (Path("data/listenbrainz/listens.json"), "ListenBrainz"),
    (Path("data/listenbrainz/feedback.json"), "LB 红心"),
    (Path("data/neodb/shelf.json"), "书影音"),
)
TOP = Path("data/lastfm/top.json")
LB_TOP = Path("data/listenbrainz/top.json")
LB_ACTIVITY = Path("data/listenbrainz/listening-activity.json")
ACTIVITIES = Path("data/workouts/activities.json")
HEALTH = Path("data/health/daily.json")


def staged_names() -> set[str]:
    raw = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT
    )
    return {name for name in raw.decode().split("\0") if name}


def added_names() -> set[str]:
    raw = subprocess.check_output(
        ["git", "diff", "--cached", "--diff-filter=A", "--name-only", "-z"],
        cwd=ROOT,
    )
    return {name for name in raw.decode().split("\0") if name}


def load_head(rel: Path):
    try:
        raw = subprocess.check_output(
            ["git", "show", f"HEAD:{rel.as_posix()}"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None
    return json.loads(raw)


def load_work(rel: Path):
    path = ROOT / rel
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def item_count(data) -> int:
    if data is None:
        return 0
    if isinstance(data, dict):
        return len(data.get("items") or [])
    if isinstance(data, list):
        return len(data)
    return 0


def list_part(rel: Path, label: str, names: set[str]) -> str | None:
    if rel.as_posix() not in names:
        return None
    delta = item_count(load_work(rel)) - item_count(load_head(rel))
    if delta:
        return f"{label} {delta:+d}"
    return f"{label}有更新"


def format_subject(prefix: str, parts: list[str]) -> str:
    if not parts:
        return prefix
    return f"{prefix}（{'，'.join(parts)}）"


def fetch_subject(names: set[str]) -> str:
    parts = [
        part
        for part in (list_part(rel, label, names) for rel, label in FETCH_LISTS)
        if part
    ]
    if TOP.as_posix() in names:
        parts.append("榜单有更新")
    if LB_TOP.as_posix() in names:
        parts.append("LB 榜单有更新")
    if LB_ACTIVITY.as_posix() in names:
        parts.append("LB 活跃有更新")
    return format_subject("chore: 同步生活数据", parts)


def garmin_subject(names: set[str], added: set[str]) -> str:
    parts = []
    activity = list_part(ACTIVITIES, "运动", names)
    if activity:
        parts.append(activity)
    health = list_part(HEALTH, "健康", names)
    if health:
        parts.append(health)
    extra = sorted(
        name
        for name in added
        if name.startswith("data/workouts/") and name != ACTIVITIES.as_posix()
    )
    if extra and ACTIVITIES.as_posix() not in names:
        parts.append(f"文件 {len(extra):+d}")
    return format_subject("chore: 更新运动归档", parts)


def self_check() -> None:
    fetch = fetch_subject(set())
    if fetch != "chore: 同步生活数据":
        raise SystemExit(f"empty fetch subject: {fetch}")
    garmin = garmin_subject(set(), set())
    if garmin != "chore: 更新运动归档":
        raise SystemExit(f"empty garmin subject: {garmin}")
    packed = format_subject("chore: 同步生活数据", ["听歌 +12", "书影音有更新"])
    if packed != "chore: 同步生活数据（听歌 +12，书影音有更新）":
        raise SystemExit(f"packed subject: {packed}")
    print("self-check ok")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
        return
    if len(sys.argv) != 2 or sys.argv[1] not in {"fetch", "garmin"}:
        raise SystemExit("usage: commit_message.py fetch|garmin")
    names = staged_names()
    if sys.argv[1] == "fetch":
        print(fetch_subject(names))
        return
    print(garmin_subject(names, added_names()))


if __name__ == "__main__":
    main()
