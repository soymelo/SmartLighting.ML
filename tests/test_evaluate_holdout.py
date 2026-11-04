"""Verifica o fluxo final com pesos congelados e um cenário pequeno de teste."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from smartlighting_ml.evaluate_holdout import evaluate_holdout
from smartlighting_ml.generate import load_scenario
from smartlighting_ml.generate import write_dataset as generate_dataset
from smartlighting_ml.prepare import write_dataset as prepare_dataset


ROOT = Path(__file__).resolve().parents[1]


class HoldoutEvaluationTests(unittest.TestCase):
    def test_frozen_model_evaluates_holdout_without_training(self) -> None:
        scenario = load_scenario(ROOT / "scenarios/holdout.json")
        scenario["sensors"] = [dict(scenario["sensors"][0], base_events_per_hour=0.0)]
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            scenario_path = root / "holdout.json"
            scenario_path.write_text(json.dumps(scenario), encoding="utf-8")
            generated, processed, output = (root / name for name in ("generated", "processed", "output"))
            generate_dataset(scenario, date(2026, 8, 1), 42, 7, generated)
            prepare_dataset(scenario, generated, processed)
            topology = root / "topology.json"
            topology.write_text(json.dumps({
                "schema_version": 1,
                "luminaires": [{"luminaire_id": "L01", "device": "A", "slot": 1,
                                "zone_ids": ["Z01"]}],
            }), encoding="utf-8")
            report = evaluate_holdout(
                scenario_path, generated, processed, ROOT / "config/firmware_model.json",
                ROOT / "config/dimming_policy.json", topology, output,
            )
            self.assertEqual(report["seed"], 7)
            self.assertEqual(report["event_count"], 0)
            self.assertEqual(report["zone"]["window_count"], 42 * 96 - 4)
            self.assertEqual(report["luminaire"]["window_count"], 42 * 96 - 4)
            self.assertEqual(report["zone"]["decisions"]["active_window_count"], 0)
            self.assertFalse(report["model_retrained_on_holdout"])
            self.assertEqual(report["fixed_standard"]["mean_rest_pwm"], 20)
            self.assertTrue((output / "window_decisions.csv").is_file())
            self.assertTrue((output / "luminaire_decisions.csv").is_file())

            scenario["scenario_id"] = "development"
            scenario_path.write_text(json.dumps(scenario), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "não conferem"):
                evaluate_holdout(
                    scenario_path, generated, processed, ROOT / "config/firmware_model.json",
                    ROOT / "config/dimming_policy.json", topology, output,
                )
