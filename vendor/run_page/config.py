import os
import subprocess
from collections import namedtuple
from pathlib import Path

# life-archive layout: this file lives in vendor/run_page/, archives in data/.
# sync_run_page.py does not overwrite this file.
# Keep path resolution in sync with scripts/jsonio.py (no cross-import).

CANONICAL_PUBLIC = "viazure/life-archive"
current = os.path.dirname(os.path.realpath(__file__))
code_root = Path(os.path.dirname(os.path.dirname(current))).resolve()


def _normalize_remote(url: str) -> str:
    text = url.strip()
    if text.endswith(".git"):
        text = text[:-4]
    if text.startswith("git@"):
        host_path = text.split("@", 1)[1]
        host, path = host_path.split(":", 1)
        text = f"https://{host}/{path}"
    text = text.removeprefix("https://").removeprefix("http://")
    if text.startswith("github.com/"):
        text = text[len("github.com/") :]
    return text.lower()


def _git_remote_url(repo: Path) -> str | None:
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        return None
    proc = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def resolve_data_root() -> Path:
    env = os.environ.get("LIFE_DATA_ROOT", "").strip()
    return Path(env).expanduser().resolve() if env else code_root


def archives_blocked(root: Path | None = None) -> bool:
    target = (root or resolve_data_root()).resolve()
    origin = _git_remote_url(code_root)
    return bool(
        origin
        and _normalize_remote(origin) == CANONICAL_PUBLIC
        and _is_within(target, code_root)
    )


def assert_can_write_archives() -> None:
    if archives_blocked():
        raise SystemExit(
            "refusing to write archives into viazure/life-archive; "
            "set LIFE_DATA_ROOT to a private data checkout, or fork this repo"
        )


root_path = resolve_data_root()
root = str(root_path)
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

if not archives_blocked(root_path):
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
