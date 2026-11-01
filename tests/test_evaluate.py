import math
import unittest
from datetime import UTC, datetime

from smartlighting_ml.evaluate import (
    calculate_metrics,
    hour_zone_predictions,
    split_chronologically,
)


class EvaluateTests(unittest.TestCase):
    def test_local_date_defines_train_test_boundary(self) -> None:
        metadata = {"start_local": "2026-08-01", "days": 2, "utc_offset_hours": -3}
        examples = [
            {"prediction_at_utc": datetime(2026, 8, 2, 2, 45, tzinfo=UTC)},
            {"prediction_at_utc": datetime(2026, 8, 2, 3, tzinfo=UTC)},
        ]
        train, test, cutoff = split_chronologically(examples, metadata, 1)
        self.assertEqual(train, examples[:1])
        self.assertEqual(test, examples[1:])
        self.assertEqual(cutoff, examples[1]["prediction_at_utc"])

    def test_hour_zone_mean_uses_only_training_targets(self) -> None:
        train = [
            {"zone_id": "Z01", "local_hour": 19, "next_15m_count": 0},
            {"zone_id": "Z01", "local_hour": 19, "next_15m_count": 2},
        ]
        test = [{"zone_id": "Z01", "local_hour": 19, "next_15m_count": 20}]
        self.assertEqual(hour_zone_predictions(train, test), [(1.0, 0.5)])

    def test_metrics_separate_count_error_from_activity_alerts(self) -> None:
        test = [{"next_15m_count": 0}, {"next_15m_count": 2}]
        metrics = calculate_metrics(test, [(0.0, 0.0), (1.0, 0.8)])
        self.assertEqual(metrics["mae"], 0.5)
        self.assertAlmostEqual(metrics["rmse"], math.sqrt(0.5))
        self.assertAlmostEqual(metrics["brier"], 0.02)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["alert_rate"], 0.5)
