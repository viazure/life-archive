#!/usr/bin/env python3
"""Build data/workouts/activities.json from FIT files plus earlier imports.

Garmin rows use the FIT sport and sub_sport strings as type and subtype.
Sessions without a route or under 100 m stay in the file; distance may be 0.
Rows already in the archive that do not match a FIT run_id are kept, so
TCX/GPX imports are not rewritten into Garmin types. New rows are taken from
.cache/activities.json when their run_id is not already present. source is
the ingest path the script can see: garmin, tcx, or gpx — not the device brand.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import polyline
from garmin_fit_sdk import Decoder, Stream
from garmin_fit_sdk.util import FIT_EPOCH_S

from jsonio import CACHE, DATA, dump, load_list

FIT_DIR = DATA / "workouts" / "fit"
TCX_DIR = DATA / "workouts" / "tcx"
GPX_DIR = DATA / "workouts" / "gpx"
DEST = DATA / "workouts" / "activities.json"
CACHE_ACTIVITIES = CACHE / "activities.json"
TCX_NS = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"
FILE_SOURCES = {"tcx", "gpx"}
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
SEMICIRCLE = 11930465


def _fit_name(value) -> str:
    if value is None:
        return ""
    text = str(value)
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text.lower()


def _seconds(session: dict, *keys: str) -> float:
    for key in keys:
        value = session.get(key)
        if value is not None:
            return float(value)
    return 0.0


def _clock(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _duration(seconds: float) -> str:
    """Keep sub-second precision. running_page stores timedelta microseconds
    (e.g. 0:58:00.962000); rounding here made PRs one second slower."""
    return str(timedelta(seconds=max(0.0, float(seconds))))


def activity_from_fit(path) -> dict | None:
    messages, _errors = Decoder(Stream.from_file(str(path))).read(
        convert_datetimes_to_dates=False
    )
    sessions = messages.get("session_mesgs") or []
    if not sessions:
        print(f"skip {path.name}: no session")
        return None
    session = sessions[0]
    start_raw = session.get("start_time")
    if start_raw is None:
        print(f"skip {path.name}: no start_time")
        return None
    start = datetime.fromtimestamp(int(start_raw) + FIT_EPOCH_S, tz=timezone.utc)
    moving_seconds = _seconds(
        session, "total_moving_time", "total_timer_time", "total_elapsed_time"
    )
    distance = session.get("total_distance")
    distance = 0.0 if distance is None else float(distance)
    points = []
    for record in messages.get("record_mesgs") or []:
        if "position_lat" in record and "position_long" in record:
            points.append(
                [
                    record["position_lat"] / SEMICIRCLE,
                    record["position_long"] / SEMICIRCLE,
                ]
            )
    heart_rate = session.get("avg_heart_rate")
    speed = session.get("enhanced_avg_speed")
    if speed is None:
        speed = session.get("avg_speed")
    if speed is None:
        speed = distance / moving_seconds if moving_seconds else 0.0
    ascent = session.get("total_ascent")
    return {
        "average_heartrate": int(heart_rate) if heart_rate is not None else None,
        "average_speed": float(speed or 0),
        "distance": distance,
        "elevation_gain": float(ascent or 0),
        "location_country": "",
        "moving_time": _duration(moving_seconds),
        "name": "",
        "run_id": int(start.timestamp() * 1000),
        "source": "garmin",
        "start_date": _clock(start),
        "start_date_local": _clock(start.astimezone(LOCAL_TZ)),
        "streak": 1,
        "subtype": _fit_name(session.get("sub_sport")),
        "summary_polyline": polyline.encode(points) if points else "",
        "type": _fit_name(session.get("sport")),
    }


def _run_id(stamp: str) -> int:
    parsed = datetime.fromisoformat(stamp.strip())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return int(parsed.timestamp() * 1000)


def _tcx_ids(path) -> set[int]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return set()
    activity = root.find(f".//{TCX_NS}Activity")
    if activity is None:
        return set()
    found = set()
    stamp = activity.find(f"{TCX_NS}Id")
    if stamp is not None and (stamp.text or "").strip():
        found.add(_run_id(stamp.text))
    first = activity.find(f".//{TCX_NS}Trackpoint/{TCX_NS}Time")
    if first is not None and (first.text or "").strip():
        found.add(_run_id(first.text))
    return found


def _gpx_id(path) -> int | None:
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag.endswith("time") and (elem.text or "").strip():
            return _run_id(elem.text)
        elem.clear()
    return None


def file_sources() -> dict[int, str]:
    """Map run_id to tcx or gpx from the archive directories."""
    found: dict[int, str] = {}
    if TCX_DIR.is_dir():
        for path in sorted(TCX_DIR.glob("*.tcx")):
            for run_id in _tcx_ids(path):
                found.setdefault(run_id, "tcx")
    if GPX_DIR.is_dir():
        for path in sorted(GPX_DIR.glob("*.gpx")):
            run_id = _gpx_id(path)
            if run_id is not None:
                found.setdefault(run_id, "gpx")
    return found


def _as_file_row(row: dict, sources: dict[int, str]) -> dict:
    copied = dict(row)
    current = copied.get("source")
    if current == "garmin":
        return copied
    detected = sources.get(copied.get("run_id"))
    if detected:
        copied["source"] = detected
    elif current not in FILE_SOURCES:
        copied.pop("source", None)
    return copied


def merge(
    existing: list[dict],
    fit_rows: list[dict],
    cache_rows: list[dict],
    sources: dict[int, str],
) -> list[dict]:
    old_by_id = {
        row.get("run_id"): row for row in existing if row.get("run_id") is not None
    }
    fit_ids = set()
    merged_fit = []
    for row in fit_rows:
        previous = old_by_id.get(row["run_id"]) or {}
        if previous.get("name"):
            row["name"] = previous["name"]
        if previous.get("location_country"):
            row["location_country"] = previous["location_country"]
        if previous.get("streak") is not None:
            row["streak"] = previous["streak"]
        merged_fit.append(row)
        fit_ids.add(row["run_id"])
    kept = [
        _as_file_row(row, sources)
        for row in existing
        if row.get("run_id") not in fit_ids
    ]
    kept_ids = fit_ids | {row.get("run_id") for row in kept}
    # running_page FIT views use type Run plus a subtype. TCX/GPX rows now
    # also have FIT subtypes, so only skip the FIT view.
    for row in cache_rows:
        run_id = row.get("run_id")
        if run_id in kept_ids:
            continue
        if str(row.get("type") or "") == "Run" and row.get("subtype"):
            continue
        kept.append(_as_file_row(row, sources))
        kept_ids.add(run_id)
    return sorted(
        merged_fit + kept,
        key=lambda row: (
            str(row.get("start_date_local") or ""),
            row.get("run_id") or 0,
        ),
    )


def main() -> None:
    if not FIT_DIR.is_dir():
        raise SystemExit(f"FIT folder not found: {FIT_DIR}")
    fit_rows = []
    for path in sorted(FIT_DIR.glob("*.fit")):
        row = activity_from_fit(path)
        if row:
            fit_rows.append(row)
    cache_rows = load_list(CACHE_ACTIVITIES)
    sources = file_sources()
    items = merge(load_list(DEST), fit_rows, cache_rows, sources)
    dump(DEST, items)
    counts = {}
    for row in items:
        key = row.get("source") or "unset"
        counts[key] = counts.get(key, 0) + 1
    summary = ", ".join(f"{count} {name}" for name, count in sorted(counts.items()))
    print(f"workouts {len(items)} ({len(fit_rows)} from FIT; {summary})")


if __name__ == "__main__":
    main()
