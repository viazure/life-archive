#!/usr/bin/env python3
"""Shared pretty JSON and HTTP helpers for life-data fetchers."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = ROOT / ".cache"
UA = "life-data/1.0"


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def load_list(path: Path) -> list:
    """Load items from a JSON array or an object with an items field."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("items") or [])
    return list(data)


def archive_envelope(source: str, items: list, **extra) -> dict:
    return {"source": source, "items": items, **extra}


def log(message: str) -> None:
    print(message, flush=True)


def request_target(url: str) -> str:
    """Host and path only, so progress lines never include query secrets."""
    parts = urllib.parse.urlsplit(url)
    return f"{parts.netloc}{parts.path}"


def _request_headers(headers: dict | None) -> dict:
    return {"User-Agent": UA, **(headers or {})}


def _curl_json(url: str, headers: dict) -> dict:
    command = ["curl", "-sS", "--max-time", "60", "-w", "\n%{http_code}"]
    if sys.platform == "win32":
        command.append("--ssl-no-revoke")
    for key, value in headers.items():
        command.extend(["-H", f"{key}: {value}"])
    command.append(url)
    proc = subprocess.run(command, capture_output=True, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise urllib.error.URLError(detail or f"curl exit {proc.returncode}")
    body, _, status_raw = proc.stdout.rpartition(b"\n")
    status = int(status_raw or "0")
    if status >= 400:
        raise urllib.error.HTTPError(url, status, f"HTTP {status}", hdrs=None, fp=None)
    return json.loads(body.decode("utf-8"))


def get_json(url: str, headers: dict | None = None) -> dict:
    headers = _request_headers(headers)
    req = urllib.request.Request(url, headers=headers)
    target = request_target(url)
    last_error = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        try:
            return _curl_json(url, headers)
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            OSError,
            ValueError,
        ) as exc:
            last_error = exc
        if attempt + 1 < 4:
            log(f"http retry {attempt + 1}/3 {target}: {last_error}")
            time.sleep(1 + attempt)
    raise urllib.error.URLError(f"{target}: {last_error}")


def text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return text(value.get("#text") or value.get("name") or "")
    return str(value).strip()


def tags_of(raw) -> list[str]:
    if not raw:
        return []
    names = []
    for tag in raw:
        if isinstance(tag, str):
            names.append(tag)
        elif isinstance(tag, dict):
            names.append(text(tag.get("name") or tag.get("title")))
    return sorted({name for name in names if name})


def self_check() -> None:
    messy = {"b": 1, "a": [{"z": 2, "y": 1}]}
    first = json.dumps(messy, ensure_ascii=False, indent=2, sort_keys=True)
    second = json.dumps(
        {"a": [{"y": 1, "z": 2}], "b": 1}, ensure_ascii=False, indent=2, sort_keys=True
    )
    if first != second:
        raise SystemExit("canonical json mismatch")
    env = archive_envelope("test", [{"id": 1}], user="u")
    if env["source"] != "test" or env["user"] != "u" or env["items"] != [{"id": 1}]:
        raise SystemExit("archive envelope mismatch")
    leaked = request_target(
        "https://ws.audioscrobbler.com/2.0/?api_key=secret&method=x"
    )
    if leaked != "ws.audioscrobbler.com/2.0/":
        raise SystemExit(f"request target leaked query: {leaked}")
    print("self-check ok")


def main() -> None:
    if "--self-check" in sys.argv:
        self_check()
        return
    raise SystemExit(
        "jsonio.py is a library; pass --self-check to verify JSON formatting"
    )


if __name__ == "__main__":
    main()
