#!/usr/bin/env python3
"""Merge device-neutral daily health metrics with that day's workouts.

Consumers read data/health/daily.json. Adapters supply metric patches.
This module does not know which device produced them.
"""

from __future__ import annotations

import sys
from collections import defaultdict

from jsonio import DATA, archive_envelope, dump, load_list, log

SOURCE = "health.daily"
DEST = DATA / "health" / "daily.json"
ACTIVITIES = DATA / "workouts" / "activities.redacted.json"

METRIC_FIELDS = (
    "active_calories",
    "avg_stress",
    "body_battery_charged",
    "body_battery_drained",
    "body_battery_high",
    "body_battery_low",
    "distance_m",
    "intensity_minutes",
    "max_hr",
    "min_hr",
    "resting_hr",
    "steps",
    "total_calories",
)
SLEEP_FIELDS = (
    "avg_respiration",
    "avg_spo2",
    "avg_stress",
    "awake_count",
    "awake_s",
    "body_battery_change",
    "deep_s",
    "duration_s",
    "end_local",
    "light_s",
    "need_min",
    "qualifier",
    "rem_s",
    "score",
    "skin_temp_c",
    "start_local",
)
HRV_FIELDS = (
    "baseline_balanced_low",
    "baseline_balanced_upper",
    "baseline_low_upper",
    "last_night_5min_high",
    "last_night_avg",
    "status",
    "weekly_avg",
)
TRAINING_FIELDS = (
    "readiness",
    "recovery_hours",
    "status",
    "vo2_max",
)
WORKOUT_FIELDS = (
    "average_heartrate",
    "average_speed",
    "distance",
    "elevation_gain",
    "moving_time",
    "name",
    "run_id",
    "source",
    "start_date_local",
    "subtype",
    "type",
)
NESTED = (
    ("sleep", SLEEP_FIELDS),
    ("hrv", HRV_FIELDS),
    ("training", TRAINING_FIELDS),
)


def blank_nested(fields: tuple[str, ...]) -> dict:
    return {key: None for key in fields}


def blank_day(day: str) -> dict:
    row = {"date": day, "metrics_source": None}
    for key in METRIC_FIELDS:
        row[key] = None
    for name, fields in NESTED:
        row[name] = blank_nested(fields)
    return row


def _copy_nested(row: dict, name: str, fields: tuple[str, ...]) -> dict:
    raw = row.get(name) if isinstance(row.get(name), dict) else {}
    return {key: raw.get(key) for key in fields}


def metric_row(row: dict) -> dict:
    """Full metric record for one date. Missing keys become null."""
    day = str(row.get("date") or "")
    copied = blank_day(day)
    copied["metrics_source"] = row.get("metrics_source")
    for key in METRIC_FIELDS:
        if key in row:
            copied[key] = row.get(key)
    for name, fields in NESTED:
        if name in row:
            copied[name] = _copy_nested(row, name, fields)
    return copied


def _local_day(row: dict) -> str | None:
    local = str(row.get("start_date_local") or "")
    day = local[:10]
    if len(day) == 10 and day[4] == "-" and day[7] == "-":
        return day
    return None


def workouts_by_date(activities: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in activities:
        day = _local_day(row)
        if day is None:
            continue
        grouped[day].append({key: row.get(key) for key in WORKOUT_FIELDS})
    for items in grouped.values():
        items.sort(
            key=lambda item: (
                str(item.get("start_date_local") or ""),
                item.get("run_id") or 0,
            )
        )
    return grouped


def _has_metrics(row: dict) -> bool:
    if row.get("metrics_source"):
        return True
    if any(row.get(key) is not None for key in METRIC_FIELDS):
        return True
    for name, fields in NESTED:
        nested = row.get(name) or {}
        if any(nested.get(key) is not None for key in fields):
            return True
    return False


def merge_days(
    existing: list[dict], updates: list[dict], activities: list[dict]
) -> list[dict]:
    """Replace metric patches by date, then attach workouts for every kept day.

    A date stays when it has health metrics or at least one workout.
    Updates replace the whole metric record for that date. Workout lists
    always come from activities, never from the patch.
    """
    by_date: dict[str, dict] = {}
    for row in existing:
        day = str(row.get("date") or "")
        if day:
            by_date[day] = metric_row(row)
    for row in updates:
        day = str(row.get("date") or "")
        if not day:
            continue
        by_date[day] = metric_row(row)
    workouts = workouts_by_date(activities)
    items = []
    for day in sorted(set(by_date) | set(workouts)):
        row = by_date.get(day) or blank_day(day)
        attached = workouts.get(day) or []
        if not _has_metrics(row) and not attached:
            continue
        row["workouts"] = attached
        items.append(row)
    return items


def write_daily(items: list[dict]) -> None:
    dump(DEST, archive_envelope(SOURCE, items))


def self_check() -> None:
    existing = [
        {
            "date": "2026-10-13",
            "metrics_source": "garmin",
            "steps": 1000,
            "sleep": {"score": 70, "ignored": True},
            "workouts": [{"run_id": 1}],
        },
        {"date": "2026-10-01", "metrics_source": "garmin", "steps": 5},
    ]
    updates = [{"date": "2026-10-13", "metrics_source": "garmin", "steps": 2000}]
    activities = [
        {
            "run_id": 9,
            "source": "tcx",
            "type": "running",
            "subtype": "generic",
            "name": "easy",
            "start_date_local": "2026-10-14 07:00:00",
            "distance": 5000,
            "moving_time": "0:30:00",
            "average_speed": 2.7,
            "average_heartrate": 140,
            "elevation_gain": 12,
            "summary_polyline": "secret",
            "location_country": "CN",
        },
        {
            "run_id": 8,
            "source": "garmin",
            "type": "training",
            "subtype": "strength_training",
            "name": "",
            "start_date_local": "2026-10-13 18:00:00",
            "distance": 0,
            "moving_time": "0:20:00",
            "average_speed": 0,
            "average_heartrate": 110,
            "elevation_gain": 0,
        },
        {"run_id": 1, "start_date_local": ""},
    ]
    items = merge_days(existing, updates, activities)
    by_date = {row["date"]: row for row in items}
    if list(by_date) != ["2026-10-01", "2026-10-13", "2026-10-14"]:
        raise SystemExit(f"day order: {list(by_date)}")
    refreshed = by_date["2026-10-13"]
    if refreshed["steps"] != 2000 or refreshed["sleep"]["score"] is not None:
        raise SystemExit(f"update did not replace metrics: {refreshed}")
    if "ignored" in refreshed["sleep"] or refreshed["workouts"][0]["run_id"] != 8:
        raise SystemExit(f"workout attach failed: {refreshed}")
    workout_only = by_date["2026-10-14"]
    if workout_only["metrics_source"] is not None or workout_only["steps"] is not None:
        raise SystemExit(f"workout-only day has metrics: {workout_only}")
    projected = workout_only["workouts"][0]
    if projected["source"] != "tcx" or "summary_polyline" in projected:
        raise SystemExit(f"projection leaked: {projected}")
    if by_date["2026-10-01"]["workouts"] != []:
        raise SystemExit("historical metrics lost their empty workout list")
    log("self-check ok")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
        return
    items = merge_days(load_list(DEST), [], load_list(ACTIVITIES))
    write_daily(items)
    log(f"health days {len(items)}")
    log(f"wrote {DEST.relative_to(DATA.parent)}")


if __name__ == "__main__":
    main()
