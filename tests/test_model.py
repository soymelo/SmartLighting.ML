import math
import unittest

from sklearn.linear_model import PoissonRegressor

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

        # Confere que a fórmula exportável devolve o mesmo valor que a biblioteca.
        matrix = []
        for row in rows:
            values = [0.0] * (len(model.weights) - 1)
            for index, value in model.features(row):
                if index:
                    values[index - 1] = value
            matrix.append(values)
        reference = PoissonRegressor(alpha=0.001, max_iter=1000, tol=1e-8)
        reference.fit(matrix, [row["next_15m_count"] for row in rows])
        self.assertAlmostEqual(model.predict(quiet)[0], reference.predict([matrix[0]])[0], places=9)
        self.assertEqual(len(model.as_dict()["feature_order"]), len(model.weights))

    def test_unknown_zone_is_rejected(self) -> None:
        model = PoissonModel(["Z01"], (15,), [0.0] * 28)
        with self.assertRaisesRegex(ValueError, "Zona desconhecida"):
            model.predict({"zone_id": "Z02", "local_hour": 19, "local_weekday": 0, "previous_15m_count": 1})
