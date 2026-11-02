import math
import unittest

from smartlighting_ml.model import PoissonModel, fit_poisson


class ModelTests(unittest.TestCase):
    def test_probability_and_nonnegative_count(self) -> None:
        model = PoissonModel(["Z01"], (15,), [0.0] * 28)
        row = {"zone_id": "Z01", "local_hour": 19, "local_weekday": 0, "previous_15m_count": 0}
        mean, probability = model.predict(row)
        self.assertEqual(mean, 1.0)
        self.assertAlmostEqual(probability, 1 - math.exp(-1))

    def test_recent_activity_can_increase_prediction(self) -> None:
        rows = []
        for day in range(30):
            for recent, target in ((0, 0), (1, 1), (3, 3)):
                rows.append({
                    "zone_id": "Z01", "local_hour": 19, "local_weekday": day % 7,
                    "previous_15m_count": recent, "next_15m_count": target,
                })
        model = fit_poisson(rows, (15,))
        quiet = dict(rows[0])
        busy = dict(rows[0], previous_15m_count=3)
        self.assertGreater(model.predict(busy)[0], model.predict(quiet)[0])
        self.assertGreater(model.predict(busy)[1], model.predict(quiet)[1])

    def test_unknown_zone_is_rejected(self) -> None:
        model = PoissonModel(["Z01"], (15,), [0.0] * 28)
        with self.assertRaisesRegex(ValueError, "Zona desconhecida"):
            model.predict({"zone_id": "Z02", "local_hour": 19, "local_weekday": 0, "previous_15m_count": 1})
