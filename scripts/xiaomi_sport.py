#!/usr/bin/env python3
"""Map Xiaomi export filenames to Garmin FIT type/subtype and backup folders."""

from __future__ import annotations

import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

TCX_NS = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"
STEM_RE = re.compile(r"^\d{8}(.+?)(?:_\d+)?$")
Z_TIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)[Zz]")
FREESTYLE_HR_CUTOFF = 110
_LOCAL_OVERRIDE = Path(__file__).resolve().parent / "local" / "stem_override.py"


def _load_stem_override() -> dict[str, tuple[str, str, str]]:
    if not _LOCAL_OVERRIDE.is_file():
        return {}
    spec = importlib.util.spec_from_file_location("stem_override", _LOCAL_OVERRIDE)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = getattr(module, "STEM_OVERRIDE", {})
    return dict(raw) if isinstance(raw, dict) else {}


STEM_OVERRIDE = _load_stem_override()

KIND_SPORT = {
    "Outdoor running": ("running", "generic"),
    "Treadmill": ("running", "treadmill"),
    "Walking": ("walking", "generic"),
    "Hiking": ("hiking", "generic"),
    "Trekking": ("hiking", "generic"),
    "Pool swimming": ("swimming", "lap_swimming"),
    "Outdoor cycling": ("cycling", "generic"),
    "Indoor cycling": ("cycling", "indoor_cycling"),
    "Jump rope": ("training", "jump_rope"),
    "Yoga": ("training", "yoga"),
    "Stair climber": ("fitness_equipment", "stair_climbing"),
    "Skateboarding": ("skateboarding", "generic"),
    "Somatosensory game": ("training", "generic"),
}

KIND_FOLDER = {
    "Outdoor running": "running",
    "Treadmill": "running",
    "Walking": "walking",
    "Hiking": "hiking",
    "Trekking": "hiking",
    "Pool swimming": "swimming",
    "Outdoor cycling": "cycling",
    "Indoor cycling": "cycling",
    "Jump rope": "training",
    "Yoga": "training",
    "Stair climber": "training",
    "Skateboarding": "training",
    "Somatosensory game": "training",
    "Freestyle": "training",
}


def kind_from_stem(stem: str) -> str:
    match = STEM_RE.match(stem)
    return match.group(1) if match else stem


def lap_hr(root: ET.Element) -> int | None:
    hearts: list[float] = []
    for lap in root.findall(f".//{TCX_NS}Lap"):
        node = lap.find(f"{TCX_NS}HeartRateBpm")
        if node is None:
            continue
        value = node.find(f"{TCX_NS}Value")
        raw = (value.text if value is not None and value.text else node.text) or ""
        if raw.strip():
            hearts.append(float(raw.strip()))
    if not hearts:
        return None
    return int(round(sum(hearts) / len(hearts)))


def sport_for_kind(kind: str, heartrate: int | None = None) -> tuple[str, str]:
    if kind in KIND_SPORT:
        return KIND_SPORT[kind]
    if kind == "Freestyle":
        if heartrate is not None and heartrate >= FREESTYLE_HR_CUTOFF:
            return "training", "generic"
        return "fitness_equipment", "pilates"
    return "training", "generic"


def activity_sport_attr(path: Path) -> str:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return ""
    activity = root.find(f".//{TCX_NS}Activity")
    if activity is None:
        return ""
    return (activity.get("Sport") or "").strip()


def keep_path(path: Path) -> bool:
    """Drop unlisted Freestyle only when a personal override file exists."""
    if kind_from_stem(path.stem) != "Freestyle":
        return True
    if not STEM_OVERRIDE:
        return True
    return path.stem in STEM_OVERRIDE


def name_for_path(path: Path) -> str:
    extra = STEM_OVERRIDE.get(path.stem)
    return extra[2] if extra else path.stem


def sport_for_path(path: Path) -> tuple[str, str]:
    extra = STEM_OVERRIDE.get(path.stem)
    if extra:
        return extra[0], extra[1]
    kind = kind_from_stem(path.stem)
    heartrate = None
    if kind == "Freestyle" and path.suffix.lower() == ".tcx":
        attr = activity_sport_attr(path)
        if attr and "run" not in attr.lower():
            mapped = KIND_SPORT.get(attr)
            if mapped:
                return mapped
        try:
            heartrate = lap_hr(ET.parse(path).getroot())
        except ET.ParseError:
            heartrate = None
    return sport_for_kind(kind, heartrate)


def backup_folder(path: Path) -> str:
    kind = kind_from_stem(path.stem)
    return KIND_FOLDER.get(kind, "training")


def rewrite_z_to_offset(text: str) -> str:
    return Z_TIME_RE.sub(r"\1+08:00", text)
