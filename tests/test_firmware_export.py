"""Confere os exemplos congelados para a futura implementação em C++."""

import json
import tempfile
import unittest
from pathlib import Path

from smartlighting_ml.export_cpp_weights import render_header
from smartlighting_ml.model import load_model


ROOT = Path(__file__).resolve().parents[1]


class FirmwareExportTests(unittest.TestCase):
    def test_cpp_header_preserves_every_selected_weight(self) -> None:
        path = ROOT / "config/firmware_model.json"
        policy_path = ROOT / "config/dimming_policy.json"
        model = load_model(path)
        header = render_header(path, policy_path)
        self.assertEqual(header, render_header(path, policy_path))
        exported = [
            float(line.strip().split(",", 1)[0])
            for line in header.splitlines() if line.startswith("    ")
        ]
        self.assertEqual(exported, model.weights)
        self.assertEqual(len(exported), 27)
        self.assertIn("constexpr int HourStartIndex = 1;", header)
        self.assertIn("constexpr int Previous30mIndex = 26;", header)
        self.assertIn("constexpr int StandardPwm = 20;", header)

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            invalid = json.loads(path.read_text(encoding="utf-8"))
            invalid["scenario_id"] = "development"
            invalid_path = Path(directory) / "wrong_model.json"
            invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "modelo geral"):
                render_header(invalid_path, policy_path)

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
