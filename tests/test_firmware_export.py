"""Confere os exemplos congelados para a futura implementação em C++."""

import json
import unittest
from pathlib import Path

from smartlighting_ml.model import load_model


ROOT = Path(__file__).resolve().parents[1]


class FirmwareExportTests(unittest.TestCase):
    def test_reference_cases_match_selected_weights_and_policy(self) -> None:
        model = load_model(ROOT / "config/firmware_model.json")
        reference = json.loads((ROOT / "config/firmware_reference.json").read_text(encoding="utf-8"))
        self.assertEqual(model.history_minutes, (30,))
        self.assertEqual(reference["scenario_id"], "persistent_activity")
        self.assertEqual(len(reference["cases"]), 8)
        for case in reference["cases"]:
            mean, probability = model.predict(case)
            self.assertAlmostEqual(mean, case["predicted_count"], places=12)
            self.assertAlmostEqual(probability, case["activity_probability"], places=12)
            thresholds = reference["probability_thresholds"]
            pwm = reference["pwm_levels"]
            expected = (pwm["high"] if probability >= thresholds["high_at"]
                        else pwm["standard"] if probability >= thresholds["standard_at"]
                        else pwm["low"])
            self.assertEqual(case["rest_pwm"], expected)
