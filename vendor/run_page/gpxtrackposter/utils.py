"""Assorted utility methods for use in creating posters."""

# Copyright 2016-2019 Florian Pigorsch & Contributors. All rights reserved.
#
# Use of this source code is governed by a MIT-style
# license that can be found in the LICENSE file.

import locale
import math
from datetime import datetime

import colour
import pytz
import s2sphere as s2

try:
    from tzfpy import get_tz as _tzfpy_get_tz

    tf = None
except ImportError:
    # tzfpy is not available, fallback to timezonefinder
    from timezonefinder import TimezoneFinder

    _tzfpy_get_tz = None
    tf = TimezoneFinder()


from .xy import XY


# mercator projection
def latlng2xy(latlng: s2.LatLng) -> XY:
    return XY(lng2x(latlng.lng().degrees), lat2y(latlng.lat().degrees))


def lng2x(lng_deg: float) -> float:
    return lng_deg / 180 + 1


def lat2y(lat_deg: float) -> float:
    return 0.5 - math.log(math.tan(math.pi / 4 * (1 + lat_deg / 90))) / math.pi


def project(
    bbox: s2.LatLngRect, size: XY, offset: XY, latlnglines: list[list[s2.LatLng]]
) -> list[list[tuple[float, float]]]:
    min_x = lng2x(bbox.lng_lo().degrees)
    d_x = lng2x(bbox.lng_hi().degrees) - min_x
    while d_x >= 2:
        d_x -= 2
    while d_x < 0:
        d_x += 2
    min_y = lat2y(bbox.lat_lo().degrees)
    max_y = lat2y(bbox.lat_hi().degrees)
    d_y = abs(max_y - min_y)
    # the distance maybe zero
    if d_x == 0 or d_y == 0:
        return []
    scale = size.x / d_x if size.x / size.y <= d_x / d_y else size.y / d_y
    offset = offset + 0.5 * (size - scale * XY(d_x, -d_y)) - scale * XY(min_x, min_y)
    lines = []
    # If len > $zoom_threshold, choose 1 point out of every $step to reduce size of the SVG file
    zoom_threshold = 400
    for latlngline in latlnglines:
        line = []
        step = int(len(latlngline) / zoom_threshold) + 1
        for i in range(0, len(latlngline), step):
            latlng = latlngline[i]
            if bbox.contains(latlng):
                line.append((offset + scale * latlng2xy(latlng)).tuple())
            else:
                if len(line) > 0:
                    lines.append(line)
                    line = []
        if len(line) > 0:
            lines.append(line)
    return lines


def compute_grid(
    count: int, dimensions: XY
) -> tuple[float | None, tuple[int, int] | None]:
    # this is somehow suboptimal O(count^2). I guess it's possible in O(count)
    min_waste = -1.0
    best_size = None
    best_counts = None
    for count_x in range(1, count + 1):
        size_x = dimensions.x / count_x
        for count_y in range(1, count + 1):
            if count_x * count_y >= count:
                size_y = dimensions.y / count_y
                size = min(size_x, size_y)
                waste = dimensions.x * dimensions.y - count * size * size
                if waste < 0:
                    continue
                elif best_size is None or waste < min_waste:
                    best_size = size
                    best_counts = count_x, count_y
                    min_waste = waste
    return best_size, best_counts


def interpolate_color(color1: str, color2: str, ratio: float) -> str:
    if ratio < 0:
        ratio = 0
    elif ratio > 1:
        ratio = 1
    c1 = colour.Color(color1)
    c2 = colour.Color(color2)
    c3 = colour.Color(
        hue=((1 - ratio) * c1.hue + ratio * c2.hue),
        saturation=((1 - ratio) * c1.saturation + ratio * c2.saturation),
        luminance=((1 - ratio) * c1.luminance + ratio * c2.luminance),
    )
    return c3.hex_l


def format_float(f):
    return locale.format_string("%.1f", f)


def _resolve_timezone_name(point) -> str:
    """Timezone from GPS point, fallback Asia/Shanghai."""
    if not point:
        return "Asia/Shanghai"
    lat, lng = point
    if _tzfpy_get_tz is not None:
        try:
            return _tzfpy_get_tz(lng=lng, lat=lat) or "Asia/Shanghai"
        except Exception as e:  # noqa: BLE001
            # just a little trick when tzfpy support windows will delete this
            print(f"tzfpy error: {e} fallback to timezonefinder")
    if tf is not None:
        return tf.timezone_at(lng=lng, lat=lat) or "Asia/Shanghai"
    return "Asia/Shanghai"


def parse_datetime_to_local(start_time, end_time, point):
    """Return naive local wall-clock datetimes for start/end.

    - Timezone-aware inputs (e.g. TCX ``...+08:00``): convert via astimezone —
      do NOT add utcoffset again (that caused a double +8h bug).
    - Naive inputs: treat as UTC-like absolute wall and add the local offset
      (previous behavior for FIT/GPX without tz).
    """
    tz_name = _resolve_timezone_name(point)
    tz = pytz.timezone(tz_name)

    if start_time.tzinfo is not None and start_time.utcoffset() is not None:
        local_start = start_time.astimezone(tz).replace(tzinfo=None)
        local_end = end_time.astimezone(tz).replace(tzinfo=None)
        return local_start, local_end

    tc_offset = datetime.now(tz).utcoffset()
    return start_time + tc_offset, end_time + tc_offset


def get_normalized_sport_type(sport_type):
    if sport_type == "Run":
        return "running"
    elif sport_type == "Walk":
        return "walking"
    elif sport_type == "Ride":
        return "cycling"
    else:
        return sport_type
