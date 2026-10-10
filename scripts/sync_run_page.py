#!/usr/bin/env python3
"""Refresh the vendored vendor/run_page/ slice from a running_page checkout.

Default source is the sibling directory ../running_page. Override with
--source. LICENSE is copied when present; NOTICE is rewritten with the
source commit. vendor/run_page/config.py is local (data/ and .cache/ paths)
and is not overwritten.

This repo keeps a trimmed copy so CI does not need a local path. After
updating your running_page fork, run:

  python scripts/sync_run_page.py
  git diff vendor/run_page
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT.parent / "running_page"
VENDOR = ROOT / "vendor" / "run_page"

# Keep in sync with the files life-data actually imports for Garmin/TCX/GPX.
# config.py stays local so archive paths are not reset to GPX_OUT/.
COPY_PATHS = (
    "run_page/garmin_sync.py",
    "run_page/get_garmin_secret.py",
    "run_page/tcx_sync.py",
    "run_page/gpx_sync.py",
    "run_page/fix_tcx_local_time.py",
    "run_page/garmin_device_adaptor.py",
    "run_page/utils.py",
    "run_page/polyline_processor.py",
    "run_page/synced_data_file_logger.py",
    "run_page/generator/__init__.py",
    "run_page/generator/db.py",
    "run_page/gpxtrackposter/track.py",
    "run_page/gpxtrackposter/track_loader.py",
    "run_page/gpxtrackposter/exceptions.py",
    "run_page/gpxtrackposter/year_range.py",
    "run_page/gpxtrackposter/utils.py",
    "run_page/gpxtrackposter/xy.py",
    "LICENSE",
)


def git(source: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=source,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"git {' '.join(args)} failed in {source}: {detail}")
    return proc.stdout.strip()


def source_meta(source: Path) -> tuple[str, str]:
    commit = git(source, "rev-parse", "HEAD")
    url = git(source, "remote", "get-url", "origin")
    if url.endswith(".git"):
        url = url[:-4]
    if url.startswith("git@"):
        # git@github.com:owner/repo -> https://github.com/owner/repo
        host_path = url.split("@", 1)[1]
        host, path = host_path.split(":", 1)
        url = f"https://{host}/{path}"
    return commit, url


def write_notice(commit: str, url: str) -> None:
    text = f"""The files in this directory are copied from
{url}
commit {commit}
and are covered by the MIT License in LICENSE
(Copyright (c) 2025 yihong).

gpxtrackposter/ includes source from Florian Pigorsch & Contributors,
Copyright 2016-2019. Those file headers point at this LICENSE.

garmin_sync.py notes that most of its code comes from
https://github.com/cyberjunky/python-garminconnect

Refresh with: python scripts/sync_run_page.py
config.py is local to life-data and is not refreshed.
"""
    (VENDOR / "NOTICE").write_text(text, encoding="utf-8")


def copy_file(source: Path, rel: str, dry_run: bool) -> None:
    src = source / rel
    if not src.is_file():
        raise SystemExit(f"missing in source: {src}")
    # LICENSE lives at running_page root; everything else is under run_page/.
    if rel == "LICENSE":
        dest_rel = "vendor/run_page/LICENSE"
    else:
        dest_rel = "vendor/" + rel
    dest = ROOT / dest_rel
    if dry_run:
        print(f"copy {rel} -> {dest_rel}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"updated {dest_rel}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"running_page checkout (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print actions without writing files",
    )
    args = parser.parse_args()
    source = args.source.resolve()
    if not (source / "run_page").is_dir():
        raise SystemExit(f"not a running_page checkout: {source}")
    if not (source / ".git").exists():
        raise SystemExit(f"source has no .git metadata: {source}")

    commit, url = source_meta(source)
    print(f"source {url} @ {commit}")
    for rel in COPY_PATHS:
        copy_file(source, rel, args.dry_run)
    if args.dry_run:
        print("NOTICE would be rewritten")
        return
    write_notice(commit, url)
    print("updated vendor/run_page/NOTICE")


if __name__ == "__main__":
    main()
