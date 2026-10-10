#!/usr/bin/env python3
"""Archive NeoDB shelf marks into neodb/shelf.json (near-raw API objects).

NEODB_TOKEN stays in the environment. When it is missing, the script skips
and exits 0. Each mark is stored as returned by the API, with shelf_type and
list category filled from the request path when absent.

NeoDB merges duplicate catalog items and redirects old uuids. The shelf list
still returns marks on those old uuids, so after fetch we resolve each item
and keep one mark per canonical uuid.
"""

from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.parse
from collections import defaultdict

from jsonio import DATA, archive_envelope, dump, get_json, load_list, log, text

NEODB_CATEGORIES = ("book", "movie", "tv", "music", "game", "podcast", "performance")
NEODB_SHELVES = ("wishlist", "progress", "complete")
SHELF_RANK = {"dropped": 0, "wishlist": 1, "progress": 2, "complete": 3}
NEODB_HOST = "https://neodb.social"


def mark_key(mark: dict) -> tuple:
    item = mark.get("item") or {}
    return (
        text(mark.get("created_time")),
        text(mark.get("shelf_type")),
        text(item.get("uuid") or mark.get("uuid")),
        text(mark.get("category") or item.get("category")),
    )


def item_uuid(mark: dict) -> str:
    item = mark.get("item") or {}
    return text(item.get("uuid") or mark.get("uuid"))


def item_request_url(mark: dict) -> str:
    item = mark.get("item") or {}
    api = text(item.get("api_url"))
    if api.startswith("http"):
        return api
    if api.startswith("/"):
        return NEODB_HOST + api
    uuid = item_uuid(mark)
    path = text(item.get("url"))
    if path.startswith("/"):
        return f"{NEODB_HOST}/api{path}"
    category = text(mark.get("category") or item.get("category"))
    if category and uuid:
        return f"{NEODB_HOST}/api/{category}/{uuid}"
    return ""


def keep_key(mark: dict) -> tuple:
    return (
        SHELF_RANK.get(text(mark.get("shelf_type")), -1),
        1 if mark.get("rating_grade") not in (None, "") else 0,
        1 if text(mark.get("comment_text")) else 0,
        text(mark.get("created_time")),
    )


def collapse_merged_marks(
    marks: list[dict], canonical_item_by_uuid: dict[str, dict]
) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for mark in marks:
        if not isinstance(mark, dict):
            continue
        src = item_uuid(mark)
        canonical = canonical_item_by_uuid.get(src)
        row = dict(mark)
        if isinstance(canonical, dict) and text(canonical.get("uuid")):
            row["item"] = canonical
            category = text(canonical.get("category"))
            if category:
                row["category"] = category
            key = text(canonical.get("uuid"))
        else:
            key = src
        if not key:
            continue
        grouped[key].append(row)
    out = [max(rows, key=keep_key) for rows in grouped.values()]
    out.sort(key=mark_key)
    return out


def resolve_canonical_items(marks: list[dict]) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    pending: list[tuple[str, str]] = []
    source_item: dict[str, dict] = {}
    for mark in marks:
        uuid = item_uuid(mark)
        if not uuid or uuid in source_item:
            continue
        source_item[uuid] = dict(mark.get("item") or {})
        pending.append((uuid, item_request_url(mark)))
    log(f"neodb resolve {len(pending)} items")
    for index, (uuid, url) in enumerate(pending, start=1):
        item = source_item.get(uuid) or {}
        if not url:
            mapping[uuid] = item
            continue
        if index == 1 or index % 50 == 0 or index == len(pending):
            log(f"neodb resolve {index}/{len(pending)} {uuid}")
        try:
            payload = get_json(url)
            if isinstance(payload, dict) and text(payload.get("uuid")):
                mapping[uuid] = payload
            else:
                mapping[uuid] = item
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            ValueError,
        ) as exc:
            log(f"neodb resolve skip {uuid}: {exc}")
            mapping[uuid] = item
        time.sleep(0.05)
    return mapping


def canonicalize_marks(marks: list[dict]) -> list[dict]:
    before = len(marks)
    collapsed = collapse_merged_marks(marks, resolve_canonical_items(marks))
    dropped = before - len(collapsed)
    if dropped:
        log(f"neodb collapsed {dropped} merged marks ({len(collapsed)} kept)")
    else:
        log("neodb no merged marks")
    return collapsed


def fetch_neodb(token: str) -> list[dict]:
    headers = {"Authorization": f"Bearer {token}"}
    items = []
    log("neodb full shelf")
    for category in NEODB_CATEGORIES:
        for shelf in NEODB_SHELVES:
            page = 1
            while True:
                log(f"neodb {category}/{shelf} page {page}")
                query = urllib.parse.urlencode(
                    {"category": category, "page": page, "page_size": 50}
                )
                url = f"{NEODB_HOST}/api/me/shelf/{shelf}?{query}"
                payload = get_json(url, headers)
                batch = payload.get("data") or payload.get("items") or []
                for mark in batch:
                    if not isinstance(mark, dict):
                        continue
                    row = dict(mark)
                    row.setdefault("shelf_type", shelf)
                    row.setdefault("category", category)
                    items.append(row)
                pages = int(payload.get("pages") or 1)
                log(
                    f"neodb {category}/{shelf} page {page}/{pages} "
                    f"(+{len(batch)}, total {len(items)})"
                )
                if page >= pages or not batch:
                    break
                page += 1
                time.sleep(0.2)
    return canonicalize_marks(items)


def write_shelf(items: list[dict]) -> None:
    dump(DATA / "neodb" / "shelf.json", archive_envelope("neodb.shelf", items))
    log(f"neodb ok ({len(items)} marks)")


def self_check() -> None:
    stub = {
        "uuid": "old",
        "category": "movie",
        "api_url": "/api/movie/old",
        "title": "Stub",
    }
    canon = {
        "uuid": "new",
        "category": "movie",
        "api_url": "/api/movie/new",
        "title": "Canonical",
        "external_resources": [{"url": "https://example.test"}],
    }
    mapping = {
        "old": canon,
        "new": canon,
        "other": {"uuid": "other", "category": "book"},
    }
    marks = [
        {
            "shelf_type": "wishlist",
            "created_time": "2025-01-01T00:00:00Z",
            "item": stub,
            "rating_grade": None,
        },
        {
            "shelf_type": "complete",
            "created_time": "2025-01-02T00:00:00Z",
            "item": canon,
            "rating_grade": 8,
        },
        {
            "shelf_type": "complete",
            "created_time": "2024-01-01T00:00:00Z",
            "item": {"uuid": "other", "category": "book"},
        },
    ]
    out = collapse_merged_marks(marks, mapping)
    if len(out) != 2:
        raise SystemExit(f"collapse count {len(out)}")
    movie = next(m for m in out if item_uuid(m) == "new")
    if movie.get("shelf_type") != "complete" or movie.get("rating_grade") != 8:
        raise SystemExit("did not keep complete mark")
    if (movie.get("item") or {}).get("title") != "Canonical":
        raise SystemExit("did not rewrite canonical item")
    if item_request_url({"item": stub}) != f"{NEODB_HOST}/api/movie/old":
        raise SystemExit("item url mismatch")
    log("self-check ok")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
        return
    try:
        if "--from-archive" in sys.argv:
            items = canonicalize_marks(load_list(DATA / "neodb" / "shelf.json"))
            write_shelf(items)
            return
        token = os.environ.get("NEODB_TOKEN", "").strip()
        if not token:
            log("NEODB_TOKEN unset, skip neodb")
            return
        write_shelf(fetch_neodb(token))
    except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
        raise SystemExit(f"neodb: {exc}") from exc


if __name__ == "__main__":
    main()
