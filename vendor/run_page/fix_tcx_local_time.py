"""
One-shot fix: TCX files with +08:00 were imported with start_date_local
shifted +8h again (double offset). For those rows, start_date already holds
the correct local wall clock — copy it to start_date_local, then rewrite
activities.json.

Usage (from repo root, with project venv):
  .venv\\Scripts\\python.exe run_page/fix_tcx_local_time.py
  .venv\\Scripts\\python.exe run_page/fix_tcx_local_time.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from config import JSON_FILE, SQL_FILE, TCX_FOLDER

TIME_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?([Zz]|[+-]\d{2}:\d{2})?"
)


def parse_tcx_wall_start(tcx_path: Path) -> datetime | None:
    """First trackpoint (or Id) wall clock from a TCX file."""
    text = tcx_path.read_text(encoding="utf-8", errors="ignore")
    for pattern in (
        r"<Time>([^<]+)</Time>",
        r"<Id>([^<]+)</Id>",
    ):
        m = re.search(pattern, text)
        if not m:
            continue
        parsed = TIME_RE.match(m.group(1).strip())
        if not parsed:
            continue
        return datetime.strptime(
            f"{parsed.group(1)} {parsed.group(2)}", "%Y-%m-%d %H:%M:%S"
        )
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing DB/JSON",
    )
    args = parser.parse_args()

    tcx_dir = Path(TCX_FOLDER)
    if not tcx_dir.is_dir():
        raise SystemExit(f"TCX folder not found: {tcx_dir}")

    walls: list[datetime] = []
    for fp in sorted(tcx_dir.glob("*.tcx")):
        wall = parse_tcx_wall_start(fp)
        if wall:
            walls.append(wall)
    if not walls:
        raise SystemExit("No TCX start times found")

    conn = sqlite3.connect(SQL_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    fixed = 0
    skipped = 0
    samples: list[tuple] = []

    for wall in walls:
        # tolerate 1s drift between Id and first Time
        candidates = []
        for delta in (0, 1, -1):
            key = (wall + timedelta(seconds=delta)).strftime("%Y-%m-%d %H:%M:%S")
            rows = cur.execute(
                "SELECT run_id, start_date, start_date_local FROM activities "
                "WHERE start_date = ?",
                (key,),
            ).fetchall()
            candidates.extend(rows)
        # de-dupe by run_id
        seen = set()
        rows = []
        for r in candidates:
            if r["run_id"] in seen:
                continue
            seen.add(r["run_id"])
            rows.append(r)

        if not rows:
            skipped += 1
            continue

        for row in rows:
            local = row["start_date_local"]
            correct = row["start_date"]
            try:
                local_dt = datetime.strptime(local, "%Y-%m-%d %H:%M:%S")
                start_dt = datetime.strptime(correct, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            # Only fix the classic double-+8 pattern
            if local_dt - start_dt != timedelta(hours=8):
                continue
            if local == correct:
                continue
            if len(samples) < 8:
                samples.append((row["run_id"], correct, local, correct))
            if not args.dry_run:
                cur.execute(
                    "UPDATE activities SET start_date_local = ? WHERE run_id = ?",
                    (correct, row["run_id"]),
                )
            fixed += 1

    if not args.dry_run:
        conn.commit()

    print(f"TCX files with parseable start: {len(walls)}")
    print(f"{'Would fix' if args.dry_run else 'Fixed'} rows: {fixed}")
    print(f"TCX with no matching start_date row: {skipped}")
    for run_id, before_date, before_local, after_local in samples:
        print(
            f"  run_id={run_id} start_date={before_date} "
            f"local {before_local} -> {after_local}"
        )

    if args.dry_run:
        conn.close()
        return

    # Patch activities.json in place so CI-only rows are preserved
    json_path = Path(JSON_FILE)
    if json_path.is_file():
        activities_list = json.loads(json_path.read_text(encoding="utf-8"))
        db_local = {
            int(r["run_id"]): r["start_date_local"]
            for r in cur.execute("SELECT run_id, start_date_local FROM activities")
        }
        patched = 0
        for a in activities_list:
            rid = int(a["run_id"])
            if rid not in db_local:
                continue
            if a.get("start_date_local") != db_local[rid]:
                a["start_date_local"] = db_local[rid]
                patched += 1
        json_path.write_text(
            json.dumps(activities_list, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Patched {patched} rows in {json_path} (total {len(activities_list)})")
    else:
        from generator import Generator

        generator = Generator(SQL_FILE)
        activities_list = generator.load()
        json_path.write_text(
            json.dumps(activities_list, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Wrote {len(activities_list)} activities -> {json_path}")

    conn.close()


if __name__ == "__main__":
    main()
