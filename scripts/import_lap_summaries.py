#!/usr/bin/env python3
"""Append lap-only TCX rows that tcx_sync could not load.

Files with trackpoints are left to tcx_sync. Files that only have a lap
summary are added to .cache/activities.json when that start time is not
already present. A single-point track with zero moving time is repaired from
the lap totals.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from jsonio import CACHE, DATA, dump, load_list
from xiaomi_sport import keep_path, name_for_path, sport_for_path

TCX_NS = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"
TCX_DIR = DATA / "workouts" / "tcx"
ACTIVITIES = CACHE / "activities.json"


def wall_and_id(stamp: str) -> tuple[str, int]:
    parsed = datetime.fromisoformat(stamp)
    wall = parsed.strftime("%Y-%m-%d %H:%M:%S")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return wall, int(parsed.timestamp() * 1000)


def lap_number(lap: ET.Element, tag: str) -> float:
    node = lap.find(f"{TCX_NS}{tag}")
    if node is None or not (node.text or "").strip():
        return 0.0
    return float(node.text.strip())


def lap_hr(lap: ET.Element) -> float | None:
    node = lap.find(f"{TCX_NS}HeartRateBpm")
    if node is None:
        return None
    value = node.find(f"{TCX_NS}Value")
    raw = (value.text if value is not None and value.text else node.text) or ""
    raw = raw.strip()
    if not raw:
        return None
    return float(raw)


def lap_totals(activity: ET.Element) -> tuple[float, int, int | None]:
    laps = activity.findall(f"{TCX_NS}Lap")
    distance = sum(lap_number(lap, "DistanceMeters") for lap in laps)
    seconds = int(round(sum(lap_number(lap, "TotalTimeSeconds") for lap in laps)))
    hearts = [hr for hr in (lap_hr(lap) for lap in laps) if hr]
    heartrate = int(round(sum(hearts) / len(hearts))) if hearts else None
    return distance, seconds, heartrate


def row_of(
    path: Path,
    wall: str,
    run_id: int,
    distance: float,
    seconds: int,
    heartrate: int | None,
    sport_type: str,
    subtype: str,
    name: str,
) -> dict:
    return {
        "average_heartrate": heartrate,
        "average_speed": distance / seconds if seconds else 0,
        "distance": distance,
        "elevation_gain": 0,
        "location_country": "",
        "moving_time": str(timedelta(seconds=seconds)),
        "name": name,
        "run_id": run_id,
        "source": "tcx",
        "start_date": wall,
        "start_date_local": wall,
        "subtype": subtype,
        "summary_polyline": "",
        "type": sport_type,
    }


def zero_duration(value) -> bool:
    return str(value or "") in {"0:00:00", "0:00:00.000000"}


def main() -> None:
    if not TCX_DIR.is_dir():
        raise SystemExit(f"TCX folder not found: {TCX_DIR}")
    items = load_list(ACTIVITIES)
    by_wall = {row.get("start_date_local"): row for row in items}
    seen_ids = {row.get("run_id") for row in items}
    added = 0
    repaired = 0
    for path in sorted(TCX_DIR.glob("*.tcx")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        activity = root.find(f".//{TCX_NS}Activity")
        stamp = activity.find(f"{TCX_NS}Id") if activity is not None else None
        if activity is None or stamp is None or not (stamp.text or "").strip():
            continue
        distance, seconds, heartrate = lap_totals(activity)
        if seconds <= 0:
            continue
        wall, run_id = wall_and_id(stamp.text.strip())
        first = activity.find(f".//{TCX_NS}Trackpoint/{TCX_NS}Time")
        first_wall = (
            wall_and_id(first.text.strip())[0]
            if first is not None and (first.text or "").strip()
            else wall
        )
        existing = by_wall.get(first_wall) or by_wall.get(wall)
        has_track = activity.find(f".//{TCX_NS}Trackpoint") is not None
        if existing is not None:
            if has_track and zero_duration(existing.get("moving_time")):
                existing["moving_time"] = str(timedelta(seconds=seconds))
                existing["average_speed"] = distance / seconds
                if existing.get("average_heartrate") in (None, 0) and heartrate:
                    existing["average_heartrate"] = heartrate
                if not existing.get("name"):
                    existing["name"] = name_for_path(path)
                repaired += 1
            continue
        if has_track or run_id in seen_ids or wall in by_wall:
            continue
        if not keep_path(path):
            continue
        sport_type, subtype = sport_for_path(path)
        row = row_of(
            path,
            wall,
            run_id,
            distance,
            seconds,
            heartrate,
            sport_type,
            subtype,
            name_for_path(path),
        )
        items.append(row)
        by_wall[wall] = row
        seen_ids.add(run_id)
        added += 1
    dump(ACTIVITIES, items)
    print(f"lap summaries added {added}, repaired {repaired}")


if __name__ == "__main__":
    main()
