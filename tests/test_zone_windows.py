import csv
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from smartlighting_ml.evaluate_dimming import WINDOW_COLUMNS
from smartlighting_ml.zone_windows import ZoneDecision, group_zone_decisions, load_zone_decisions

ROOT = Path(__file__).resolve().parents[1]


def decision(zone: str, low: float = 0.10, minute: int = 0) -> ZoneDecision:
    utc_time = datetime(2026, 8, 22, 3, minute, tzinfo=UTC)
    return ZoneDecision(
        "development", zone, utc_time, utc_time.astimezone(timezone(timedelta(hours=-3))),
        low, 0.25, 0.12, 0, 20,
    )


class ZoneWindowsTests(unittest.TestCase):
    def test_groups_six_zones_for_each_time_and_candidate(self) -> None:
        zones = frozenset(f"Z{number:02}" for number in range(1, 7))
        rows = [decision(zone, low, minute) for low in (0.05, 0.10)
                for minute in (0, 15) for zone in zones]
        groups = group_zone_decisions(list(reversed(rows)), zones)
        self.assertEqual(len(groups), 4)
        self.assertTrue(all(set(group.decisions) == zones for group in groups))
        self.assertEqual({group.low_below_probability for group in groups}, {0.05, 0.10})
        self.assertEqual({group.prediction_at_utc.minute for group in groups}, {0, 15})

    def test_rejects_duplicate_missing_and_extra_zone(self) -> None:
        zones = frozenset({"Z01", "Z02"})
        complete = [decision("Z01"), decision("Z02")]
        for rows in (complete + [decision("Z01")], complete[:1], complete + [decision("Z99")]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                group_zone_decisions(rows, zones)

    def test_rejects_candidate_with_missing_time(self) -> None:
        zones = frozenset({"Z01", "Z02"})
        rows = [decision(zone, 0.05, minute) for minute in (0, 15) for zone in zones]
        rows.extend(decision(zone, 0.10) for zone in zones)
        with self.assertRaisesRegex(ValueError, "horários inconsistentes"):
            group_zone_decisions(rows, zones)

    def test_rejects_time_gap_and_changed_history_between_candidates(self) -> None:
        zones = frozenset({"Z01", "Z02"})
        rows = [decision(zone, low, minute) for low in (0.05, 0.10)
                for minute in (0, 30) for zone in zones]
        with self.assertRaisesRegex(ValueError, "lacuna"):
            group_zone_decisions(rows, zones)
        rows = [decision(zone, low) for low in (0.05, 0.10) for zone in zones]
        rows[-1] = replace(rows[-1], observed_next_15m_count=1)
        with self.assertRaisesRegex(ValueError, "histórico difere"):
            group_zone_decisions(rows, zones)

    def test_reads_csv_and_rejects_incoherent_local_time(self) -> None:
        row = dict.fromkeys(WINDOW_COLUMNS, "0")
        row.update({
            "scenario_id": "development", "zone_id": "Z01",
            "prediction_at_utc": "2026-08-22T03:00:00Z",
            "prediction_at_local": "2026-08-22T00:00:00-03:00",
            "activity_probability": "0.12", "low_below_probability": "0.10",
            "high_at_probability": "0.25", "rest_pwm": "20",
        })
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "decisions.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=WINDOW_COLUMNS)
                writer.writeheader()
                writer.writerow(row)
            loaded = load_zone_decisions(path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].prediction_at_local.hour, 0)
            row["prediction_at_local"] = "2026-08-22T01:00:00-03:00"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=WINDOW_COLUMNS)
                writer.writeheader()
                writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "linha 2"):
                load_zone_decisions(path)
