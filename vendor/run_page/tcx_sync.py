#!/usr/bin/env python3
"""
If you do not want bind any account
Only the gpx files in GPX_OUT sync
"""

from config import JSON_FILE, SQL_FILE, TCX_FOLDER, assert_can_write_archives

from utils import make_activities_file

if __name__ == "__main__":
    assert_can_write_archives()
    print("only sync tcx files in data/workouts/tcx")
    make_activities_file(SQL_FILE, TCX_FOLDER, JSON_FILE, file_suffix="tcx")
