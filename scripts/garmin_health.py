#!/usr/bin/env python3
"""Fill data/health/daily.json from a Garmin Connect China session.

Authentication matches vendor/run_page/garmin_sync.py: garth loads
GARMIN_SECRET_STRING_CN. This file only maps Garmin payloads onto the
device-neutral daily record. Merge and workout attachment live in
health_daily.py.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

os.environ["GARTH_TELEMETRY_ENABLED"] = "false"

from health_daily import (  # noqa: E402
    ACTIVITIES,
    DEST,
    HRV_FIELDS,
    METRIC_FIELDS,
    SLEEP_FIELDS,
    TRAINING_FIELDS,
    blank_day,
    blank_nested,
    merge_days,
    metric_row,
    write_daily,
)
from jsonio import load_list, log  # noqa: E402

LOCAL_TZ = timezone(timedelta(hours=8))
BACKFILL_DAYS = 90
REFRESH_DAYS = 14
SUMMARY_FIELDS = METRIC_FIELDS


def camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def key_names(name: str) -> tuple[str, ...]:
    camel_name = camel(name)
    names = [name, camel_name]
    if camel_name.endswith("Dto"):
        names.append(camel_name[:-3] + "DTO")
    return tuple(names)


def pick(mapping, name: str):
    if not isinstance(mapping, dict) or not name:
        return None
    for key in key_names(name):
        if key in mapping:
            return mapping[key]
    return None


def as_number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    if number.is_integer():
        return int(number)
    return number


def local_clock(value) -> str | None:
    """Garmin local timestamps are the wall clock stored as UTC."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000.0
        return datetime.fromtimestamp(seconds, timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    text = str(value).strip().replace("T", " ")
    if text.endswith("Z"):
        text = text[:-1]
    if "." in text:
        text = text.split(".", 1)[0]
    if len(text) >= 19:
        return text[:19]
    return text or None


def fields(value) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    names = getattr(value, "__dataclass_fields__", None)
    if not names:
        return None
    mapped = {}
    for name in names:
        child = getattr(value, name)
        if getattr(child, "__dataclass_fields__", None):
            mapped[name] = fields(child)
        else:
            mapped[name] = child
    return mapped


def intensity_minutes(moderate, vigorous):
    """Garmin intensity minutes count vigorous time twice."""
    if moderate is None and vigorous is None:
        return None
    return int(moderate or 0) + 2 * int(vigorous or 0)


def summary_metrics(raw: dict) -> dict:
    moderate = as_number(pick(raw, "moderate_intensity_minutes"))
    vigorous = as_number(pick(raw, "vigorous_intensity_minutes"))
    return {
        "steps": as_number(pick(raw, "total_steps")),
        "distance_m": as_number(pick(raw, "total_distance_meters")),
        "active_calories": as_number(pick(raw, "active_kilocalories")),
        "total_calories": as_number(pick(raw, "total_kilocalories")),
        "intensity_minutes": intensity_minutes(moderate, vigorous),
        "resting_hr": as_number(pick(raw, "resting_heart_rate")),
        "min_hr": as_number(pick(raw, "min_heart_rate")),
        "max_hr": as_number(pick(raw, "max_heart_rate")),
        "avg_stress": as_number(pick(raw, "average_stress_level")),
        "body_battery_high": as_number(pick(raw, "body_battery_highest_value")),
        "body_battery_low": as_number(pick(raw, "body_battery_lowest_value")),
        "body_battery_charged": as_number(pick(raw, "body_battery_charged_value")),
        "body_battery_drained": as_number(pick(raw, "body_battery_drained_value")),
    }


def _sleep_dto(raw: dict) -> dict:
    dto = pick(raw, "daily_sleep_dto")
    return dto if isinstance(dto, dict) else raw


def sleep_metrics(raw: dict | None) -> dict:
    row = blank_nested(SLEEP_FIELDS)
    if not raw:
        return row
    dto = _sleep_dto(raw)
    scores = pick(dto, "sleep_scores")
    overall = pick(scores, "overall") if isinstance(scores, dict) else None
    need = pick(dto, "sleep_need")
    spo2 = pick(raw, "wellness_sp_o2_sleep_summary_dto")
    row.update(
        {
            "start_local": local_clock(pick(dto, "sleep_start_timestamp_local")),
            "end_local": local_clock(pick(dto, "sleep_end_timestamp_local")),
            "duration_s": as_number(pick(dto, "sleep_time_seconds")),
            "deep_s": as_number(pick(dto, "deep_sleep_seconds")),
            "light_s": as_number(pick(dto, "light_sleep_seconds")),
            "rem_s": as_number(pick(dto, "rem_sleep_seconds")),
            "awake_s": as_number(pick(dto, "awake_sleep_seconds")),
            "awake_count": as_number(pick(dto, "awake_count")),
            "score": as_number(
                pick(overall, "value") if isinstance(overall, dict) else None
            ),
            "qualifier": _text(
                pick(overall, "qualifier_key") if isinstance(overall, dict) else None
            ),
            "avg_spo2": as_number(pick(dto, "average_sp_o2_value"))
            or as_number(
                pick(spo2, "average_sp_o2") if isinstance(spo2, dict) else None
            ),
            "avg_respiration": as_number(pick(dto, "average_respiration_value")),
            "avg_stress": as_number(pick(dto, "avg_sleep_stress")),
            "need_min": as_number(
                pick(need, "actual") if isinstance(need, dict) else None
            ),
            "body_battery_change": as_number(pick(raw, "body_battery_change")),
            "skin_temp_c": as_number(pick(raw, "avg_skin_temp_deviation_c")),
        }
    )
    return row


def hrv_metrics(raw: dict | None) -> dict:
    row = blank_nested(HRV_FIELDS)
    if not raw:
        return row
    summary = pick(raw, "hrv_summary")
    if not isinstance(summary, dict):
        summary = raw
    baseline = pick(summary, "baseline")
    if not isinstance(baseline, dict):
        baseline = {}
    status = pick(summary, "status")
    row.update(
        {
            "last_night_avg": as_number(pick(summary, "last_night_avg")),
            "last_night_5min_high": as_number(pick(summary, "last_night_5_min_high")),
            "weekly_avg": as_number(pick(summary, "weekly_avg")),
            "status": _text(status),
            "baseline_low_upper": as_number(pick(baseline, "low_upper")),
            "baseline_balanced_low": as_number(pick(baseline, "balanced_low")),
            "baseline_balanced_upper": as_number(pick(baseline, "balanced_upper")),
        }
    )
    return row


def _readiness_entry(raw) -> dict | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, list) or not raw:
        return None
    morning = [
        item
        for item in raw
        if isinstance(item, dict)
        and pick(item, "input_context") == "AFTER_WAKEUP_RESET"
    ]
    chosen = morning[-1] if morning else raw[-1]
    return chosen if isinstance(chosen, dict) else None


def readiness_metrics(raw) -> dict:
    row = blank_nested(TRAINING_FIELDS)
    entry = _readiness_entry(raw)
    if not entry:
        return row
    row["readiness"] = as_number(pick(entry, "score"))
    row["recovery_hours"] = as_number(pick(entry, "recovery_time"))
    return row


def training_status_metrics(raw: dict | None) -> dict:
    phrase = None
    vo2 = None
    if isinstance(raw, dict):
        recent = raw.get("mostRecentTrainingStatus") or raw.get(
            "most_recent_training_status"
        )
        latest = (
            recent.get("latestTrainingStatusData") if isinstance(recent, dict) else None
        )
        if not isinstance(latest, dict) and isinstance(recent, dict):
            latest = recent
        if isinstance(latest, dict):
            phrase = latest.get("trainingStatusFeedbackPhrase")
            if phrase is None:
                phrase = latest.get("trainingStatus")
            vo2_block = latest.get("vo2Max") or latest.get("vo2_max") or {}
            generic = vo2_block.get("generic") if isinstance(vo2_block, dict) else None
            if isinstance(generic, dict):
                vo2 = generic.get("vo2MaxPreciseValue", generic.get("vo2MaxValue"))
        if vo2 is None:
            recent_vo2 = (
                raw.get("mostRecentVO2Max") or raw.get("most_recent_vo2_max") or {}
            )
            generic = (
                recent_vo2.get("generic") if isinstance(recent_vo2, dict) else None
            )
            if isinstance(generic, dict):
                vo2 = generic.get("vo2MaxPreciseValue", generic.get("vo2MaxValue"))
    return {"status": _text(phrase), "vo2_max": as_number(vo2)}


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def dates_ending(end: date, days: int) -> list[str]:
    start = end - timedelta(days=days - 1)
    found = []
    cursor = start
    while cursor <= end:
        found.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return found


def dates_to_fetch(
    existing: list[dict], end: date, backfill: int, refresh: int
) -> list[str]:
    """Retry uncovered days inside the backfill window, and always refresh recent days.

    A day counts as covered only when metrics_source is set. A partial
    backfill therefore keeps filling gaps outside the refresh window.
    """
    covered = {
        str(row.get("date"))
        for row in existing
        if row.get("date") and row.get("metrics_source")
    }
    refresh_days = set(dates_ending(end, refresh))
    wanted = []
    seen = set()
    for day in dates_ending(end, max(backfill, refresh)):
        if day in covered and day not in refresh_days:
            continue
        if day in seen:
            continue
        seen.add(day)
        wanted.append(day)
    return wanted


def apply_section(row: dict, names: tuple[str, ...], values: dict) -> None:
    for name in names:
        row[name] = values.get(name)


def _retryable(exc: Exception) -> bool:
    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    return status == 429 or "429" in str(exc)


def call(label: str, day: str, fn):
    for attempt in (1, 2):
        try:
            return True, fn()
        except Exception as exc:  # noqa: BLE001
            if attempt == 1 and _retryable(exc):
                log(f"{label} {day} rate limited, retry")
                time.sleep(5)
                continue
            log(f"{label} {day} failed: {exc}")
            return False, None
    return False, None


def fetch_summary(garth, day: str):
    return call(
        "summary",
        day,
        lambda: garth.connectapi(
            f"/usersummary-service/usersummary/daily/?calendarDate={day}"
        ),
    )


def fetch_sleep(garth, day: str):
    def load():
        try:
            parsed = garth.DailySleepData.get(day)
        except Exception:
            parsed = None
        if parsed is not None:
            return fields(parsed)
        raw = garth.connectapi(f"/sleep-service/sleep/dailySleepData?date={day}")
        if not isinstance(raw, dict):
            return None
        dto = raw.get("dailySleepDTO") or raw.get("daily_sleep_dto") or {}
        if (
            isinstance(dto, dict)
            and not dto.get("id")
            and not dto.get("sleepTimeSeconds")
        ):
            return None
        return raw

    return call("sleep", day, load)


def fetch_hrv(garth, day: str):
    def load():
        try:
            parsed = garth.HRVData.get(day)
        except Exception:
            parsed = None
        if parsed is not None:
            mapped = fields(parsed) or {}
            mapped.pop("hrv_readings", None)
            return mapped
        raw = garth.connectapi(f"/hrv-service/hrv/{day}")
        if not raw:
            return None
        if isinstance(raw, dict):
            raw = dict(raw)
            raw.pop("hrvReadings", None)
            raw.pop("hrv_readings", None)
        return raw

    return call("hrv", day, load)


def fetch_readiness(garth, day: str):
    def load():
        try:
            parsed = garth.TrainingReadinessData.get(day)
        except Exception:
            parsed = None
        if parsed:
            return [fields(item) for item in parsed]
        raw = garth.connectapi(f"/metrics-service/metrics/trainingreadiness/{day}")
        return raw or None

    return call("readiness", day, load)


def fetch_status(garth, day: str):
    return call(
        "training",
        day,
        lambda: garth.connectapi(
            f"/metrics-service/metrics/trainingstatus/aggregated/{day}"
        ),
    )


def collect_day(garth, day: str, previous: dict | None) -> tuple[dict, bool]:
    row = metric_row(previous) if previous else blank_day(day)
    row["date"] = day
    row["metrics_source"] = "garmin"
    ok_any = False
    ok, summary = fetch_summary(garth, day)
    if ok:
        ok_any = True
        if isinstance(summary, dict):
            apply_section(row, SUMMARY_FIELDS, summary_metrics(summary))
        else:
            apply_section(row, SUMMARY_FIELDS, summary_metrics({}))
    ok, sleep = fetch_sleep(garth, day)
    if ok:
        ok_any = True
        row["sleep"] = sleep_metrics(sleep if isinstance(sleep, dict) else None)
    ok, hrv = fetch_hrv(garth, day)
    if ok:
        ok_any = True
        row["hrv"] = hrv_metrics(hrv if isinstance(hrv, dict) else None)
    training = dict(row.get("training") or blank_nested(TRAINING_FIELDS))
    ok, readiness = fetch_readiness(garth, day)
    if ok:
        ok_any = True
        mapped = readiness_metrics(readiness)
        training["readiness"] = mapped["readiness"]
        training["recovery_hours"] = mapped["recovery_hours"]
    ok, status = fetch_status(garth, day)
    if ok:
        ok_any = True
        mapped = training_status_metrics(status if isinstance(status, dict) else None)
        training["status"] = mapped["status"]
        training["vo2_max"] = mapped["vo2_max"]
    row["training"] = {key: training.get(key) for key in TRAINING_FIELDS}
    return row, ok_any


def login(secret: str, is_cn: bool):
    import garth

    if is_cn:
        garth.configure(domain="garmin.cn", ssl_verify=False)
    garth.client.loads(secret)
    token = garth.client.oauth2_token
    if token is not None and token.expired:
        garth.client.refresh_oauth2()
    return garth


def self_check() -> None:
    stamp = int(datetime(2023, 7, 19, 23, 25, tzinfo=timezone.utc).timestamp() * 1000)
    if local_clock(stamp) != "2023-07-19 23:25:00":
        raise SystemExit(f"local clock: {local_clock(stamp)}")
    if local_clock("2023-07-20T06:11:00.0") != "2023-07-20 06:11:00":
        raise SystemExit("iso local clock mismatch")
    summary = summary_metrics(
        {
            "totalSteps": 8000,
            "totalDistanceMeters": 6200.4,
            "activeKilocalories": 400,
            "totalKilocalories": 2100,
            "moderateIntensityMinutes": 22,
            "vigorousIntensityMinutes": 8,
            "restingHeartRate": 52,
            "minHeartRate": 48,
            "maxHeartRate": 156,
            "averageStressLevel": 28,
            "bodyBatteryHighestValue": 90,
            "bodyBatteryLowestValue": 18,
            "bodyBatteryChargedValue": 60,
            "bodyBatteryDrainedValue": 70,
        }
    )
    if summary["steps"] != 8000 or summary["intensity_minutes"] != 38:
        raise SystemExit(f"summary map: {summary}")
    if summary["distance_m"] != 6200.4 or summary["body_battery_charged"] != 60:
        raise SystemExit(f"summary numbers: {summary}")
    sleep = sleep_metrics(
        {
            "dailySleepDTO": {
                "sleepTimeSeconds": 25000,
                "deepSleepSeconds": 5400,
                "lightSleepSeconds": 14000,
                "remSleepSeconds": 4800,
                "awakeSleepSeconds": 800,
                "awakeCount": 2,
                "sleepStartTimestampLocal": stamp,
                "sleepEndTimestampLocal": "2023-07-20T06:11:00.0",
                "averageSpO2Value": 95.2,
                "averageRespirationValue": 14.2,
                "avgSleepStress": 18,
                "sleepScores": {"overall": {"value": 78, "qualifierKey": "GOOD"}},
                "sleepNeed": {"actual": 470, "baseline": 450},
            },
            "bodyBatteryChange": 42,
            "avgSkinTempDeviationC": -0.4,
        }
    )
    if sleep["score"] != 78 or sleep["qualifier"] != "GOOD" or sleep["need_min"] != 470:
        raise SystemExit(f"sleep map: {sleep}")
    if sleep["start_local"] != "2023-07-19 23:25:00" or sleep["skin_temp_c"] != -0.4:
        raise SystemExit(f"sleep clock: {sleep}")
    hrv = hrv_metrics(
        {
            "hrvSummary": {
                "lastNightAvg": 42,
                "lastNight5MinHigh": 66,
                "weeklyAvg": 39,
                "status": "BALANCED",
                "baseline": {"lowUpper": 36, "balancedLow": 39, "balancedUpper": 52},
            },
            "hrvReadings": [{"hrvValue": 1}],
        }
    )
    if hrv["last_night_avg"] != 42 or hrv["baseline_low_upper"] != 36:
        raise SystemExit(f"hrv map: {hrv}")
    if hrv["baseline_balanced_low"] != 39 or hrv["status"] != "BALANCED":
        raise SystemExit(f"hrv baseline: {hrv}")
    readiness = readiness_metrics(
        [
            {"score": 40, "recoveryTime": 30, "inputContext": "UPDATE"},
            {"score": 72, "recoveryTime": 18, "inputContext": "AFTER_WAKEUP_RESET"},
        ]
    )
    if readiness["readiness"] != 72 or readiness["recovery_hours"] != 18:
        raise SystemExit(f"readiness map: {readiness}")
    status = training_status_metrics(
        {
            "mostRecentTrainingStatus": {
                "latestTrainingStatusData": {
                    "trainingStatusFeedbackPhrase": "PRODUCTIVE",
                    "vo2Max": {"generic": {"vo2MaxPreciseValue": 48.5}},
                }
            }
        }
    )
    if status["status"] != "PRODUCTIVE" or status["vo2_max"] != 48.5:
        raise SystemExit(f"status map: {status}")
    empty = sleep_metrics(None)
    if empty["duration_s"] is not None or set(empty) != set(SLEEP_FIELDS):
        raise SystemExit("empty sleep is not a full null record")
    today = date(2026, 10, 15)
    if dates_to_fetch(
        [{"metrics_source": None, "date": "2026-10-15"}], today, 3, 1
    ) != dates_ending(today, 3):
        raise SystemExit("missing metrics_source should stay in the backfill")
    partial = [
        {"date": "2026-10-15", "metrics_source": "garmin"},
        {"date": "2026-10-14", "metrics_source": "garmin"},
        {"date": "2026-10-11", "metrics_source": "garmin"},
    ]
    if dates_to_fetch(partial, today, 5, 2) != [
        "2026-10-12",
        "2026-10-13",
        "2026-10-14",
        "2026-10-15",
    ]:
        raise SystemExit(
            f"partial backfill gaps: {dates_to_fetch(partial, today, 5, 2)}"
        )
    full = [{"date": day, "metrics_source": "garmin"} for day in dates_ending(today, 5)]
    if dates_to_fetch(full, today, 5, 2) != ["2026-10-14", "2026-10-15"]:
        raise SystemExit("covered backfill should refresh only")
    days = dates_ending(today, 3)
    if days != ["2026-10-13", "2026-10-14", "2026-10-15"]:
        raise SystemExit(f"date window: {days}")
    for key in SUMMARY_FIELDS:
        if key not in METRIC_FIELDS:
            raise SystemExit(f"summary field {key} is not in the daily contract")
    log("self-check ok")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
        return
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "secret_string",
        nargs="?",
        help="garth session string; defaults to GARMIN_SECRET_STRING_CN",
    )
    parser.add_argument(
        "--is-cn",
        dest="is_cn",
        action="store_true",
        help="if garmin account is cn",
    )
    parser.add_argument("--backfill", type=int, default=BACKFILL_DAYS)
    parser.add_argument("--refresh", type=int, default=REFRESH_DAYS)
    options = parser.parse_args()
    secret = options.secret_string or os.environ.get("GARMIN_SECRET_STRING_CN")
    if not secret:
        log("GARMIN_SECRET_STRING_CN unset, skip garmin health")
        return
    existing = load_list(DEST)
    days = dates_to_fetch(
        existing,
        datetime.now(LOCAL_TZ).date(),
        options.backfill,
        options.refresh,
    )
    previous = {str(row.get("date")): row for row in existing}
    garth = login(secret, options.is_cn)
    updates = []
    fetched = 0
    for day in days:
        row, ok = collect_day(garth, day, previous.get(day))
        if ok:
            updates.append(row)
            fetched += 1
        else:
            log(f"health {day} unchanged")
    if not updates:
        raise SystemExit("garmin health: no days fetched")
    items = merge_days(existing, updates, load_list(ACTIVITIES))
    write_daily(items)
    log(f"health days {len(items)} ({fetched} fetched)")
    log(f"wrote {DEST.relative_to(DEST.parents[2])}")


if __name__ == "__main__":
    main()
