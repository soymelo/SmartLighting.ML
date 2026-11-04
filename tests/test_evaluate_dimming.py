import unittest
from datetime import UTC, datetime, timedelta

from smartlighting_ml.dimming_policy import DimmingPolicy
from smartlighting_ml.evaluate_dimming import compare_thresholds
from smartlighting_ml.model import PoissonModel


class DimmingEvaluationTests(unittest.TestCase):
    def test_same_predictions_are_compared_across_thresholds(self) -> None:
        weights = [0.0] * 27
        weights[0] = -3.22
        weights[-1] = 1.0
        model = PoissonModel((30,), weights)
        start = datetime(2026, 8, 22, tzinfo=UTC)
        rows = [
            {
                "zone_id": "Z01", "prediction_at_utc": start + index * timedelta(minutes=15),
                "local_hour": 21, "local_weekday": 5,
                "previous_15m_count": 0, "previous_30m_count": recent,
                "previous_60m_count": recent, "next_15m_count": actual,
            }
            for index, (recent, actual) in enumerate(((0, 0), (1, 1), (3, 1), (7, 1)))
        ]
        policy = DimmingPolicy(10, 20, 50, 0.10, 0.25)
        records, summaries = compare_thresholds(rows, model, policy, (0.05, 0.10, 0.15), "example", -3)
        self.assertEqual(len(records), 12)
        self.assertEqual([summary["levels"]["low"]["windows"] for summary in summaries], [1, 2, 3])
        self.assertEqual([summary["levels"]["low"]["active"] for summary in summaries], [0, 1, 2])
        self.assertEqual(summaries[1]["levels"]["high"]["windows"], 1)
        self.assertEqual(summaries[1]["mean_rest_pwm_per_zone_window"], 22.5)
        self.assertEqual(summaries[1]["fixed_standard_pwm_per_zone_window"], 20)
        self.assertEqual(records[1]["observed_next_15m_count"], 1)
        self.assertEqual(records[0]["prediction_at_local"], "2026-08-21T21:00:00-03:00")

        changed_targets = [dict(row, next_15m_count=0) for row in rows]
        changed_records, _ = compare_thresholds(changed_targets, model, policy, (0.10,), "example", -3)
        self.assertEqual(
            [row["activity_probability"] for row in records[4:8]],
            [row["activity_probability"] for row in changed_records],
        )

    def test_rejects_invalid_thresholds(self) -> None:
        policy = DimmingPolicy(10, 20, 50, 0.10, 0.25)
        model = PoissonModel((30,), [0.0] * 27)
        row = {
            "zone_id": "Z01", "prediction_at_utc": datetime(2026, 8, 22, tzinfo=UTC),
            "local_hour": 21, "local_weekday": 5,
            "previous_15m_count": 0, "previous_30m_count": 0,
            "previous_60m_count": 0, "next_15m_count": 0,
        }
        for thresholds in ((0.25,), (0.10, 0.10), (0.0,)):
            with self.subTest(thresholds=thresholds), self.assertRaises(ValueError):
                compare_thresholds([row], model, policy, thresholds, "example", -3)
