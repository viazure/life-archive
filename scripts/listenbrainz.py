#!/usr/bin/env python3
"""Archive ListenBrainz listens, tops, feedback, and listening activity.

No token is required. Set LISTENBRAINZ_USER to the account name. When it is
missing, the script skips and exits 0. A missing user (HTTP 404) skips too.
Payloads are stored near-raw as returned by ListenBrainz.

By default every section runs. Pass --only to limit the work:

  python scripts/listenbrainz.py --only listens
  python scripts/listenbrainz.py --only top
  python scripts/listenbrainz.py --only feedback
  python scripts/listenbrainz.py --only activity
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import urllib.error
import urllib.parse

from jsonio import (
    DATA,
    archive_envelope,
    dump,
    get_json,
    load_list,
    log,
    text,
)

API = "https://api.listenbrainz.org/1"

LB_RANGES = (
    "this_week",
    "this_month",
    "this_year",
    "week",
    "month",
    "year",
    "all_time",
)
TOP_KINDS = (
    ("artists", "artists", "artists"),
    ("release_groups", "release-groups", "release_groups"),
    ("recordings", "recordings", "recordings"),
)


def ymd(ts: int) -> str:
    if not ts:
        return "none"
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def listen_key(row: dict) -> tuple:
    meta = row.get("track_metadata") or {}
    return (
        int(row.get("listened_at") or 0),
        text(meta.get("artist_name")),
        text(meta.get("track_name")),
    )


def fetch_listens(user: str) -> None:
    path = DATA / "listenbrainz" / "listens.json"
    existing = load_list(path)
    watermark = max((int(row.get("listened_at") or 0) for row in existing), default=0)
    if existing:
        log(
            f"listenbrainz listens incremental, {len(existing)} stored, after {ymd(watermark)}"
        )
    else:
        log("listenbrainz listens full history")
    fresh = []
    max_ts = None
    page = 0
    while True:
        page += 1
        params = {"count": 1000}
        if watermark:
            params["min_ts"] = watermark
        if max_ts:
            params["max_ts"] = max_ts
        url = (
            f"{API}/user/{urllib.parse.quote(user)}/listens?"
            f"{urllib.parse.urlencode(params)}"
        )
        bound = f" through {ymd(max_ts)}" if max_ts else ""
        log(f"listenbrainz listens page {page}{bound}")
        payload = get_json(url)
        batch = (payload.get("payload") or {}).get("listens") or []
        if not batch:
            log(f"listenbrainz listens page {page} empty")
            break
        added = 0
        for row in batch:
            if not isinstance(row, dict):
                continue
            if int(row.get("listened_at") or 0) > watermark:
                fresh.append(row)
                added += 1
        oldest = min(int(row.get("listened_at") or 0) for row in batch)
        log(
            f"listenbrainz listens page {page} got {len(batch)}, "
            f"+{added} new, oldest {ymd(oldest)}"
        )
        if len(batch) < 1000 or oldest <= watermark:
            break
        max_ts = oldest
        time.sleep(1)
    by_key = {}
    for row in existing + fresh:
        by_key[listen_key(row)] = row
    items = [by_key[key] for key in sorted(by_key)]
    log(f"listenbrainz listens writing {len(items)}")
    dump(path, archive_envelope("listenbrainz.listens", items, user=user))
    log(f"listenbrainz listens ok ({len(items)} listens, +{len(fresh)} new)")


def fetch_top_range(user: str, path_kind: str, item_key: str, range_name: str) -> list:
    url = (
        f"{API}/stats/user/{urllib.parse.quote(user)}/{path_kind}?"
        f"{urllib.parse.urlencode({'range': range_name, 'count': 50})}"
    )
    try:
        payload = get_json(url)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        log(f"listenbrainz top {item_key} {range_name} skip: {exc}")
        return []
    body = payload.get("payload") or {}
    items = body.get(item_key) or []
    return [item for item in items if isinstance(item, dict)]


def fetch_tops(user: str) -> None:
    payload_out = {
        "source": "listenbrainz.top",
        "user": user,
    }
    for kind, path_kind, item_key in TOP_KINDS:
        periods = {}
        for range_name in LB_RANGES:
            log(f"listenbrainz top {kind} {range_name}")
            periods[range_name] = fetch_top_range(user, path_kind, item_key, range_name)
            time.sleep(0.25)
        payload_out[kind] = periods
    dump(DATA / "listenbrainz" / "top.json", payload_out)
    log("listenbrainz top ok")


def feedback_key(row: dict) -> tuple:
    return (
        int(row.get("created") or 0),
        text(row.get("recording_mbid")),
        text(row.get("recording_msid")),
        int(row.get("score") or 0),
    )


def fetch_feedback(user: str) -> None:
    items = []
    offset = 0
    count = 100
    while True:
        log(f"listenbrainz feedback offset {offset}")
        url = (
            f"{API}/feedback/user/{urllib.parse.quote(user)}/get-feedback?"
            f"{urllib.parse.urlencode({'count': count, 'offset': offset})}"
        )
        payload = get_json(url)
        batch = payload.get("feedback") or []
        for row in batch:
            if isinstance(row, dict):
                items.append(row)
        total = int(payload.get("total_count") or 0)
        if not batch or offset + len(batch) >= total:
            break
        offset += len(batch)
        time.sleep(0.25)
    items.sort(key=feedback_key)
    dump(
        DATA / "listenbrainz" / "feedback.json",
        archive_envelope("listenbrainz.feedback", items, user=user),
    )
    log(f"listenbrainz feedback ok ({len(items)} items)")


def fetch_activity(user: str) -> None:
    log("listenbrainz listening-activity all_time")
    url = (
        f"{API}/stats/user/{urllib.parse.quote(user)}/listening-activity?"
        f"{urllib.parse.urlencode({'range': 'all_time'})}"
    )
    payload = get_json(url)
    body = dict(payload.get("payload") or {})
    body["source"] = "listenbrainz.listening-activity"
    body["user"] = user
    dump(DATA / "listenbrainz" / "listening-activity.json", body)
    rows = body.get("listening_activity") or []
    log(f"listenbrainz listening-activity ok ({len(rows)} buckets)")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="unused; listenbrainz has no local helpers to verify",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=("listens", "top", "feedback", "activity"),
        help="run only these sections; may be repeated. default: all",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_check:
        raise SystemExit(
            "listenbrainz has no self-check; run scripts/jsonio.py --self-check"
        )
    user = os.environ.get("LISTENBRAINZ_USER", "").strip()
    if not user:
        log("LISTENBRAINZ_USER unset, skip listenbrainz")
        return
    sections = set(args.only or ("listens", "top", "feedback", "activity"))
    try:
        if "listens" in sections:
            fetch_listens(user)
        if "top" in sections:
            fetch_tops(user)
        if "feedback" in sections:
            fetch_feedback(user)
        if "activity" in sections:
            fetch_activity(user)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            log(f"listenbrainz user {user} not found, skip")
            return
        raise SystemExit(f"listenbrainz: {exc}") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
        raise SystemExit(f"listenbrainz: {exc}") from exc


if __name__ == "__main__":
    main()
