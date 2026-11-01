import csv
import json
import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from smartlighting_ml.generate import load_scenario
from smartlighting_ml.generate import write_dataset as generate_dataset
from smartlighting_ml.prepare import (
    build_examples,
    build_windows,
    read_events,
    write_dataset,
)

ROOT = Path(__file__).resolve().parents[1]


class PrepareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = load_scenario(ROOT / "scenarios" / "development.json")
        self.metadata = {"start_local": "2026-09-01", "days": 1, "event_count": 3}
        self.start = datetime(2026, 9, 1, 3, tzinfo=UTC)

    def test_zero_windows_and_boundary_events(self) -> None:
        from datetime import timedelta

        events = [
            ("Z01", self.start + timedelta(minutes=14)),
            ("Z01", self.start + timedelta(minutes=15)),
            ("Z02", self.start + timedelta(minutes=15)),
        ]
        windows = build_windows(events, self.scenario, self.metadata)
        self.assertEqual(len(windows), 6 * 96)
        zone1 = [row for row in windows if row["zone_id"] == "Z01"]
        zone2 = [row for row in windows if row["zone_id"] == "Z02"]
        self.assertEqual([row["activation_count"] for row in zone1[:3]], [1, 1, 0])
        self.assertEqual([row["activation_count"] for row in zone2[:3]], [0, 1, 0])

    def test_examples_use_only_completed_windows(self) -> None:
        windows = build_windows([], self.scenario, self.metadata)
        zone1 = [row for row in windows if row["zone_id"] == "Z01"]
        for index, count in enumerate([1, 2, 3, 4, 99]):
            zone1[index]["activation_count"] = count
        first = next(row for row in build_examples(windows, self.scenario) if row["zone_id"] == "Z01")
        self.assertEqual(first["prediction_at_utc"], "2026-09-01T04:00:00Z")
        self.assertEqual(first["previous_15m_count"], 4)
        self.assertEqual(first["previous_60m_count"], 10)
        self.assertEqual(first["next_15m_count"], 99)
        self.assertEqual(first["local_hour"], 1)

    def test_generated_dataset_preserves_zero_counts_and_origin(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            generated = Path(directory) / "generated"
            processed = Path(directory) / "processed"
            generate_dataset(self.scenario, date(2026, 9, 1), 1, 42, generated)
            windows_path, examples_path = write_dataset(self.scenario, generated, processed)
            with windows_path.open(encoding="utf-8", newline="") as stream:
                windows = list(csv.DictReader(stream))
            with examples_path.open(encoding="utf-8", newline="") as stream:
                examples = list(csv.DictReader(stream))
            summary = json.loads((processed / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["window_count"], 6 * 96)
            self.assertEqual(summary["example_count"], 6 * 92)
            self.assertEqual(summary["source"], "synthetic")
            self.assertEqual(sum(int(row["activation_count"]) for row in windows), summary["event_count"])
            self.assertEqual(sum(int(row["activation_count"]) == 0 for row in windows), summary["zero_window_count"])
            self.assertEqual(len(examples), 6 * 92)

    def test_rejects_sensor_zone_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            generated = Path(directory)
            generate_dataset(self.scenario, date(2026, 9, 1), 1, 42, generated)
            metadata = json.loads((generated / "metadata.json").read_text(encoding="utf-8"))
            invalid = dict(self.scenario)
            invalid["sensors"] = [dict(sensor) for sensor in self.scenario["sensors"]]
            invalid["sensors"][0]["zone_id"] = "WRONG"
            with self.assertRaisesRegex(ValueError, "Sensor ou zona"):
                read_events(generated / "sensor_events.csv", invalid, metadata)

    def test_rejects_events_from_an_older_scenario(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            generated = Path(directory) / "generated"
            generate_dataset(self.scenario, date(2026, 9, 1), 1, 42, generated)
            changed = dict(self.scenario)
            changed["hour_multipliers"] = list(self.scenario["hour_multipliers"])
            changed["hour_multipliers"][19] += 0.1
            with self.assertRaisesRegex(ValueError, "não conferem"):
                write_dataset(changed, generated, Path(directory) / "processed")

    def test_persistent_scenario_uses_the_same_preparation(self) -> None:
        scenario = load_scenario(ROOT / "scenarios" / "persistent_activity.json")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            generated = Path(directory) / "generated"
            processed = Path(directory) / "processed"
            generate_dataset(scenario, date(2026, 9, 1), 1, 42, generated)
            write_dataset(scenario, generated, processed)
            metadata = json.loads((processed / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["window_count"], 6 * 96)
            self.assertEqual(metadata["example_count"], 6 * 92)
            with (processed / "examples.csv").open(encoding="utf-8", newline="") as stream:
                self.assertNotIn("persistent_activity", csv.DictReader(stream).fieldnames)
