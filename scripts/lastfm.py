#!/usr/bin/env python3
"""Archive Last.fm scrobbles, tops, and loved tracks (near-raw API objects).

LASTFM_API_KEY and LASTFM_USER stay in the environment. When either is
missing, the script skips and exits 0. Now-playing rows and tracks without a
timestamp are dropped. Track/artist/album payloads are stored as returned by
Last.fm (including #text nodes).

By default every section runs. Pass --only to limit the work:

  python scripts/lastfm.py --only scrobbles
  python scripts/lastfm.py --only top
  python scripts/lastfm.py --only loved
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


def ymd(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


LASTFM_PERIODS = ("overall", "7day", "1month", "3month", "6month", "12month")
TOP_KINDS = (
    ("artists", "user.getTopArtists", "topartists", "artist"),
    ("albums", "user.getTopAlbums", "topalbums", "album"),
    ("tracks", "user.getTopTracks", "toptracks", "track"),
)


def lastfm_call(api_key: str, method: str, **params) -> dict:
    query = urllib.parse.urlencode(
        {"method": method, "api_key": api_key, "format": "json", **params}
    )
    return get_json(f"https://ws.audioscrobbler.com/2.0/?{query}")


def as_list(value) -> list:
    if not value:
        return []
    if isinstance(value, dict):
        return [value]
    return list(value)


def scrobble_uts(track: dict) -> int | None:
    if (track.get("@attr") or {}).get("nowplaying") == "true":
        return None
    date = track.get("date") or {}
    uts = date.get("uts")
    if uts in (None, ""):
        return None
    return int(uts)


def scrobble_key(track: dict) -> tuple:
    return (
        scrobble_uts(track) or 0,
        text(track.get("artist")),
        text(track.get("name")),
        text(track.get("album")),
    )


def fetch_lastfm_window(api_key: str, user: str, start: int, end: int) -> list[dict]:
    log(f"lastfm scrobbles {ymd(start)}..{ymd(end)}")
    first = lastfm_call(
        api_key,
        "user.getRecentTracks",
        user=user,
        limit=200,
        page=1,
        extended=1,
        **{"from": start, "to": end},
    )
    attr = (first.get("recenttracks") or {}).get("@attr") or {}
    total_pages = int(attr.get("totalPages") or 1)
    if total_pages > 25 and end - start > 86400:
        mid = start + (end - start) // 2
        log(f"lastfm scrobbles split {ymd(start)}..{ymd(end)} ({total_pages} pages)")
        left = fetch_lastfm_window(api_key, user, start, mid)
        right = fetch_lastfm_window(api_key, user, mid, end)
        return left + right
    found = []
    for page in range(1, total_pages + 1):
        if page > 1:
            log(f"lastfm scrobbles {ymd(start)}..{ymd(end)} page {page}/{total_pages}")
        payload = (
            first
            if page == 1
            else lastfm_call(
                api_key,
                "user.getRecentTracks",
                user=user,
                limit=200,
                page=page,
                extended=1,
                **{"from": start, "to": end},
            )
        )
        for track in as_list((payload.get("recenttracks") or {}).get("track")):
            if not isinstance(track, dict):
                continue
            if scrobble_uts(track) is None:
                continue
            found.append(track)
        time.sleep(0.25)
    return found


def merge_scrobbles(existing: list[dict], fresh: list[dict]) -> list[dict]:
    by_key = {}
    for row in existing + fresh:
        by_key[scrobble_key(row)] = row
    return [by_key[key] for key in sorted(by_key)]


def fetch_scrobbles(api_key: str, user: str) -> None:
    scrobble_path = DATA / "lastfm" / "scrobbles.json"
    existing = load_list(scrobble_path)
    watermark = 0
    for row in existing:
        uts = scrobble_uts(row)
        if uts and uts > watermark:
            watermark = uts
    start = watermark + 1 if watermark else 1104537600  # 2005-01-01 UTC
    end = int(time.time())
    if watermark:
        log(
            f"lastfm scrobbles incremental, {len(existing)} stored, after {ymd(watermark)}"
        )
    else:
        log("lastfm scrobbles full history from 2005-01-01")
    fresh = fetch_lastfm_window(api_key, user, start, end) if start < end else []
    items = merge_scrobbles(existing, fresh)
    dump(
        scrobble_path,
        archive_envelope("lastfm.scrobbles", items, user=user),
    )
    log(f"lastfm scrobbles ok ({len(items)} tracks, +{len(fresh)} new)")


def fetch_tops(api_key: str, user: str) -> None:
    payload_out = {
        "source": "lastfm.top",
        "user": user,
    }
    for kind, method, wrapper, item_key in TOP_KINDS:
        periods = {}
        for period in LASTFM_PERIODS:
            log(f"lastfm top {kind} {period}")
            payload = lastfm_call(api_key, method, user=user, period=period, limit=50)
            periods[period] = [
                item
                for item in as_list((payload.get(wrapper) or {}).get(item_key))
                if isinstance(item, dict)
            ]
            time.sleep(0.25)
        payload_out[kind] = periods
    dump(DATA / "lastfm" / "top.json", payload_out)
    log("lastfm top ok")


def loved_uts(track: dict) -> int | None:
    date = track.get("date") or {}
    uts = date.get("uts")
    if uts in (None, ""):
        return None
    return int(uts)


def loved_key(track: dict) -> tuple:
    return (
        loved_uts(track) or 0,
        text(track.get("artist")),
        text(track.get("name")),
    )


def fetch_loved(api_key: str, user: str) -> None:
    items = []
    page = 1
    while True:
        log(f"lastfm loved page {page}")
        payload = lastfm_call(
            api_key, "user.getLovedTracks", user=user, limit=200, page=page
        )
        batch = as_list((payload.get("lovedtracks") or {}).get("track"))
        for track in batch:
            if isinstance(track, dict) and loved_uts(track) is not None:
                items.append(track)
        pages = int(
            ((payload.get("lovedtracks") or {}).get("@attr") or {}).get("totalPages")
            or 1
        )
        if page >= pages or not batch:
            break
        page += 1
        time.sleep(0.25)
    items.sort(key=loved_key)
    dump(
        DATA / "lastfm" / "loved.json",
        archive_envelope("lastfm.loved", items, user=user),
    )
    log(f"lastfm loved ok ({len(items)} tracks)")


def self_check() -> None:
    a = {
        "name": "t",
        "artist": {"#text": "a"},
        "album": {"#text": ""},
        "date": {"uts": "2"},
        "loved": "0",
    }
    b = {
        "name": "u",
        "artist": {"#text": "b"},
        "album": {"#text": "c"},
        "date": {"uts": "1"},
    }
    c = {
        "name": "t",
        "artist": {"#text": "a"},
        "album": {"#text": ""},
        "date": {"uts": "2"},
        "loved": "1",
        "mbid": "x",
    }
    merged = merge_scrobbles([a], [b, c])
    if [scrobble_uts(row) for row in merged] != [1, 2]:
        raise SystemExit("scrobble merge order mismatch")
    if merged[1].get("mbid") != "x" or merged[1].get("loved") != "1":
        raise SystemExit("scrobble merge should keep newer raw fields")
    playing = {
        "@attr": {"nowplaying": "true"},
        "name": "x",
        "artist": {"#text": "y"},
    }
    if scrobble_uts(playing) is not None:
        raise SystemExit("nowplaying was kept")
    print("self-check ok")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="verify merge/nowplaying helpers without calling the API",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=("scrobbles", "top", "loved"),
        help="run only these sections; may be repeated. default: all",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_check:
        self_check()
        return
    api_key = os.environ.get("LASTFM_API_KEY", "").strip()
    if not api_key:
        log("LASTFM_API_KEY unset, skip lastfm")
        return
    user = os.environ.get("LASTFM_USER", "").strip()
    if not user:
        log("LASTFM_USER unset, skip lastfm")
        return
    sections = set(args.only or ("scrobbles", "top", "loved"))
    try:
        if "scrobbles" in sections:
            fetch_scrobbles(api_key, user)
        if "top" in sections:
            fetch_tops(api_key, user)
        if "loved" in sections:
            fetch_loved(api_key, user)
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
        raise SystemExit(f"lastfm: {exc}") from exc


if __name__ == "__main__":
    main()
