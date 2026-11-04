import json
import math
import tempfile
import unittest
from pathlib import Path

from smartlighting_ml.model import PoissonModel
from smartlighting_ml.dimming_policy import load_policy

ROOT = Path(__file__).resolve().parents[1]


class DimmingPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / "config" / "dimming_policy.json"
        self.policy = load_policy(self.path)

    def test_probability_boundaries_choose_expected_pwm(self) -> None:
        self.assertEqual((self.policy.standard_at, self.policy.high_at), (0.05, 0.25))
        standard_at = self.policy.standard_at
        high_at = self.policy.high_at
        cases = (
            (0.0, "low", self.policy.low_pwm),
            (standard_at / 2, "low", self.policy.low_pwm),
            (standard_at, "standard", self.policy.standard_pwm),
            ((standard_at + high_at) / 2, "standard", self.policy.standard_pwm),
            (high_at, "high", self.policy.high_pwm),
            (1.0, "high", self.policy.high_pwm),
        )
        for probability, level, pwm in cases:
            with self.subTest(probability=probability):
                self.assertEqual(self.policy.level_for_probability(probability), level)
                self.assertEqual(self.policy.pwm_for_probability(probability), pwm)

    def test_rejects_invalid_probability(self) -> None:
        for probability in (-0.1, 1.1, float("nan"), float("inf"), True):
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                self.policy.pwm_for_probability(probability)

    def test_rejects_nonascending_pwm_or_thresholds(self) -> None:
        for change in (
            {"pwm_levels": {"low": 30, "standard": 20, "high": 50}},
            {"probability_thresholds": {"standard_at": 0.30, "high_at": 0.25}},
        ):
            data = json.loads(self.path.read_text(encoding="utf-8")) | change
            with tempfile.TemporaryDirectory(dir=ROOT) as directory:
                path = Path(directory) / "invalid.json"
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_policy(path)

    def test_config_change_does_not_require_model_retraining(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        changed_low = self.policy.low_pwm + 1
        data["pwm_levels"]["low"] = changed_low
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "changed.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            changed = load_policy(path)
            self.assertEqual(changed.pwm_for_probability(0.0), changed_low)
            self.assertEqual(changed.pwm_for_probability(changed.standard_at), self.policy.standard_pwm)

    def test_model_probability_can_drive_policy(self) -> None:
        weights = [0.0] * 27
        weights[0] = math.log(0.04)
        weights[-1] = 1.0
        model = PoissonModel((30,), weights)
        row = {"zone_id": "Z01", "local_hour": 19, "local_weekday": 0, "previous_30m_count": 0}
        quiet_probability = model.predict(row)[1]
        busy_probability = model.predict(row | {"previous_30m_count": 7})[1]
        self.assertEqual(self.policy.pwm_for_probability(quiet_probability), self.policy.low_pwm)
        self.assertEqual(self.policy.pwm_for_probability(busy_probability), self.policy.high_pwm)
