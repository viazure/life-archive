import os
from collections import namedtuple

# life-data layout: this file lives in vendor/run_page/, archives in data/.
# sync_run_page.py does not overwrite this file.
current = os.path.dirname(os.path.realpath(__file__))
root = os.path.dirname(os.path.dirname(current))
workouts = os.path.join(root, "data", "workouts")
cache = os.path.join(root, ".cache")

OUTPUT_DIR = os.path.join(cache, "activities")
GPX_FOLDER = os.path.join(workouts, "gpx")
TCX_FOLDER = os.path.join(workouts, "tcx")
FIT_FOLDER = os.path.join(workouts, "fit")
PNG_FOLDER = os.path.join(cache, "png")
ENDOMONDO_FILE_DIR = os.path.join(cache, "Workouts")
FOLDER_DICT = {
    "gpx": GPX_FOLDER,
    "tcx": TCX_FOLDER,
    "fit": FIT_FOLDER,
}
SQL_FILE = os.path.join(cache, "data.db")
JSON_FILE = os.path.join(cache, "activities.json")
SYNCED_FILE = os.path.join(cache, "imported.json")

for path in (
    cache,
    GPX_FOLDER,
    TCX_FOLDER,
    FIT_FOLDER,
    os.path.dirname(JSON_FILE),
):
    os.makedirs(path, exist_ok=True)

BASE_TIMEZONE = "Asia/Shanghai"
UTC_TIMEZONE = "UTC"

start_point = namedtuple("start_point", "lat lon")
run_map = namedtuple("polyline", "summary_polyline")
