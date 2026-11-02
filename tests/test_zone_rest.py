import math
import unittest

from smartlighting_ml.dimming_policy import DimmingPolicy
from smartlighting_ml.model import PoissonModel
from smartlighting_ml.zone_rest import decide_zone_rest


class ZoneRestTests(unittest.TestCase):
    def setUp(self) -> None:
        weights = [0.0] * 27
        weights[0] = math.log(0.04)
        weights[-1] = 1.0
        self.model = PoissonModel([], (30,), weights, use_zone=False)
        self.policy = DimmingPolicy(10, 20, 50, 0.05, 0.25)
        self.row = {"zone_id": "Z_NOVA", "local_hour": 19, "local_weekday": 0, "previous_30m_count": 0}

    def test_new_zone_starts_at_standard_then_uses_model(self) -> None:
        for minutes in (0, 15, 29):
            with self.subTest(minutes=minutes):
                decision = decide_zone_rest(self.model, self.policy, None, minutes)
                self.assertEqual((decision.pwm, decision.source, decision.activity_probability),
                                 (20, "insufficient_history", None))
        quiet = decide_zone_rest(self.model, self.policy, self.row, 30)
        moderate = decide_zone_rest(self.model, self.policy, self.row | {"previous_30m_count": 1}, 30)
        busy = decide_zone_rest(self.model, self.policy, self.row | {"previous_30m_count": 7}, 30)
        self.assertEqual((quiet.pwm, quiet.source), (10, "model"))
        self.assertEqual((moderate.pwm, moderate.source), (20, "model"))
        self.assertEqual((busy.pwm, busy.source), (50, "model"))

    def test_rejects_invalid_history_and_missing_observation(self) -> None:
        for minutes in (-1, True, 15.5):
            with self.subTest(minutes=minutes), self.assertRaises(ValueError):
                decide_zone_rest(self.model, self.policy, None, minutes)
        with self.assertRaises(ValueError):
            decide_zone_rest(self.model, self.policy, None, 30)
