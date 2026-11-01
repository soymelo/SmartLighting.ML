import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from smartlighting_ml.generate import generate_events, load_scenario, write_dataset


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
        start_utc = datetime(2026, 9, 1, 3, tzinfo=timezone.utc)
        end_utc = start_utc + timedelta(days=4)
        sensor_ids = {sensor["sensor_id"] for sensor in self.scenario["sensors"]}
        for event in events:
            occurred = datetime.fromisoformat(event["occurred_at_utc"].replace("Z", "+00:00"))
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


if __name__ == "__main__":
    unittest.main()
