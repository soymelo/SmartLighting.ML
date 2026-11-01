import json
import tempfile
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from smartlighting_ml.generate import (
    _persistent_schedule,
    generate_events,
    load_scenario,
    write_dataset,
)

ROOT = Path(__file__).resolve().parents[1]


class GenerateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = load_scenario(ROOT / "scenarios" / "development.json")

    def test_same_seed_reproduces_events(self) -> None:
        first = generate_events(self.scenario, date(2026, 9, 1), 5, 42)
        second = generate_events(self.scenario, date(2026, 9, 1), 5, 42)
        self.assertEqual(first, second)
        self.assertNotEqual(first, generate_events(self.scenario, date(2026, 9, 1), 5, 43))

    def test_events_have_unique_ids_and_belong_to_requested_period(self) -> None:
        events = generate_events(self.scenario, date(2026, 9, 1), 4, 42)
        identifiers = {event["event_identifier"] for event in events}
        self.assertEqual(len(events), len(identifiers))
        start_utc = datetime(2026, 9, 1, 3, tzinfo=UTC)
        end_utc = start_utc + timedelta(days=4)
        sensor_ids = {sensor["sensor_id"] for sensor in self.scenario["sensors"]}
        for event in events:
            occurred = datetime.fromisoformat(event["occurred_at_utc"])
            self.assertTrue(start_utc <= occurred < end_utc)
            self.assertIn(event["sensor_id"], sensor_ids)
            self.assertEqual(event["scenario_id"], "development")

    def test_output_identifies_synthetic_origin(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            events_path, metadata_path = write_dataset(
                self.scenario, date(2026, 9, 1), 2, 42, Path(directory)
            )
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["source"], "synthetic")
            self.assertEqual(metadata["event_count"], len(events_path.read_text(encoding="utf-8").splitlines()) - 1)

    def test_duplicate_sensor_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "invalid.json"
            scenario = dict(self.scenario)
            scenario["sensors"] = [self.scenario["sensors"][0]] * 2
            path.write_text(json.dumps(scenario), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sensor_id"):
                load_scenario(path)

    def test_zero_rate_produces_no_activations(self) -> None:
        scenario = dict(self.scenario)
        scenario["sensors"] = [dict(self.scenario["sensors"][0])]
        scenario["sensors"][0]["base_events_per_hour"] = 0
        self.assertEqual(generate_events(scenario, date(2026, 9, 1), 1, 42), [])

    def test_persistent_period_last_multiple_windows(self) -> None:
        scenario = load_scenario(ROOT / "scenarios" / "persistent_activity.json")
        schedule = _persistent_schedule(scenario, 2, 42)
        self.assertEqual(len(schedule), 2 * 96)
        starts = [
            index for index in range(1, len(schedule) - 2)
            if "Z01" in schedule[index] and "Z01" not in schedule[index - 1]
        ]
        self.assertTrue(starts)
        for index in starts:
            self.assertTrue(all("Z01" in schedule[next_index] for next_index in range(index, index + 3)))
            if index + 5 < len(schedule):
                self.assertTrue(any(
                    "Z01" not in schedule[next_index] for next_index in range(index + 3, index + 6)
                ))

    def test_persistent_events_are_reproducible(self) -> None:
        scenario = load_scenario(ROOT / "scenarios" / "persistent_activity.json")
        first = generate_events(scenario, date(2026, 9, 1), 2, 42)
        self.assertEqual(first, generate_events(scenario, date(2026, 9, 1), 2, 42))
        self.assertTrue(first)
        self.assertEqual(len(first), len({event["event_identifier"] for event in first}))
        self.assertEqual({event["scenario_id"] for event in first}, {"persistent_activity"})

    def test_invalid_persistent_parameters_are_rejected(self) -> None:
        scenario = load_scenario(ROOT / "scenarios" / "persistent_activity.json")
        for key, value in (
            ("start_probability_per_window", 1.5),
            ("min_duration_windows", 1),
            ("max_duration_windows", 2),
            ("rate_multiplier", 0.5),
        ):
            with self.subTest(key=key), tempfile.TemporaryDirectory(dir=ROOT) as directory:
                invalid = dict(scenario)
                invalid["persistent_activity"] = dict(scenario["persistent_activity"])
                invalid["persistent_activity"][key] = value
                path = Path(directory) / "invalid.json"
                path.write_text(json.dumps(invalid), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, key):
                    load_scenario(path)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            invalid = dict(scenario)
            invalid["persistent_activity"] = None
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(TypeError, "persistent_activity"):
                load_scenario(path)


if __name__ == "__main__":
    unittest.main()
