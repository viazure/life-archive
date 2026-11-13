# -*- coding: utf-8 -*-
"""Unit tests for distance vs time-bucketed split charts. No FIT files required."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor" / "run_page"))

import gen_splits  # noqa: E402


def _rec(t: float, d: float | None, hr: float | None, speed: float | None = None) -> dict:
    return {
        "t": t,
        "d": d,
        "speed": speed,
        "hr": hr,
        "cad": None,
        "power": None,
        "alt": None,
        "vo": None,
        "gct": None,
        "gctb": None,
        "vr": None,
        "step": None,
        "temp": None,
        "resp": None,
    }


class TestBuildChart(unittest.TestCase):
    def test_distance_chart_unchanged_when_distance_advances(self):
        recs = [_rec(i, float(i * 50), 120 + (i % 5), speed=3.0) for i in range(40)]
        chart = gen_splits.build_chart(recs)
        self.assertIsNotNone(chart)
        self.assertIn("hr", chart)
        self.assertIn("d", chart)
        self.assertGreater(chart["d"][-1], chart["d"][0])
        # Positive distance must not take the time-only path: d advances
        total = recs[-1]["d"] - recs[0]["d"]
        self.assertGreater(total, 0)
        # Re-running is stable
        again = gen_splits.build_chart(recs)
        self.assertEqual(chart, again)

    def test_zero_distance_falls_back_to_time_hr_in_order(self):
        # Rising HR over 400s, distance stuck at 0 (indoor strength).
        recs = [_rec(float(i), 0.0, 80 + i // 4) for i in range(401)]
        chart = gen_splits.build_chart(recs)
        self.assertIsNotNone(chart)
        hr = [x for x in chart["hr"] if x is not None]
        self.assertGreaterEqual(len(hr), 2)
        self.assertLessEqual(len(hr), gen_splits.MAX_CHART_POINTS + 2)
        self.assertEqual(hr[0], min(hr))
        self.assertEqual(hr[-1], max(hr))
        self.assertGreater(hr[-1], hr[0])
        # Time axis is chronological and starts near 0
        self.assertGreater(chart["t"][-1], chart["t"][0])
        self.assertLess(chart["t"][0], 20)

    def test_missing_distance_still_charts_hr(self):
        recs = [_rec(float(i), None, 90 + (i // 10)) for i in range(120)]
        # build_chart sees d as None; total distance 0 → time path
        chart = gen_splits.build_chart(recs)
        self.assertIsNotNone(chart)
        hr = [x for x in chart["hr"] if x is not None]
        self.assertGreater(len(hr), 2)
        self.assertGreater(hr[-1], hr[0])

    def test_too_few_records_is_none(self):
        self.assertIsNone(gen_splits.build_chart([_rec(0, 0, 100)]))
        self.assertIsNone(gen_splits.build_chart([]))


class TestRecordsKeepIndoor(unittest.TestCase):
    def test_records_keep_zero_and_missing_distance(self):
        class Timer:
            def at(self, ts: float) -> float:
                return ts

        msgs = {
            "record_mesgs": [
                {"timestamp": 1, "distance": 0, "heart_rate": 90},
                {"timestamp": 2, "distance": 0, "heart_rate": 100},
                {"timestamp": 3, "heart_rate": 110},  # distance omitted
            ]
        }
        recs = gen_splits._records(msgs, False, Timer())
        self.assertEqual(len(recs), 3)
        self.assertEqual([r["hr"] for r in recs], [90, 100, 110])


class TestAnalyzeMessagesIndoor(unittest.TestCase):
    def test_zero_total_distance_still_returns_chart(self):
        msgs = {
            "session_mesgs": [
                {
                    "start_time": 1000,
                    "total_distance": 0.0,
                    "total_timer_time": 120,
                    "sport": "training",
                    "sub_sport": "strength_training",
                }
            ],
            "record_mesgs": [
                {"timestamp": 1000 + i, "distance": 0, "heart_rate": 80 + i} for i in range(120)
            ],
            "event_mesgs": [],
        }
        out = gen_splits.analyze_messages(msgs)
        self.assertIsNotNone(out)
        self.assertIsNotNone(out["chart"])
        hr = [x for x in out["chart"]["hr"] if x is not None]
        self.assertGreater(hr[-1], hr[0])

    def test_missing_total_distance_still_analyzes(self):
        msgs = {
            "session_mesgs": [{"start_time": 1000, "total_timer_time": 30, "sport": "hiit"}],
            "record_mesgs": [
                {"timestamp": 1000 + i, "heart_rate": 100 + i} for i in range(30)
            ],
            "event_mesgs": [],
        }
        out = gen_splits.analyze_messages(msgs)
        self.assertIsNotNone(out)
        self.assertIsNotNone(out.get("chart"))


if __name__ == "__main__":
    unittest.main()
