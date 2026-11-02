import unittest
from datetime import UTC, datetime, timedelta, timezone

from smartlighting_ml.evaluate_luminaires import (
    build_luminaire_decisions,
    summarize_luminaire_decisions,
)
from smartlighting_ml.topology import Luminaire, Topology
from smartlighting_ml.zone_windows import ZoneDecision, ZoneWindow


def make_window(minute: int, zone_pwm: dict[str, int], observed: dict[str, int]) -> ZoneWindow:
    utc_time = datetime(2026, 8, 22, 3, minute, tzinfo=UTC)
    local_time = utc_time.astimezone(timezone(timedelta(hours=-3)))
    decisions = {
        zone: ZoneDecision("development", zone, utc_time, local_time, 0.10, 0.25,
                           0.12, observed[zone], pwm)
        for zone, pwm in zone_pwm.items()
    }
    return ZoneWindow("development", utc_time, local_time, 0.10, 0.25, decisions)


class LuminaireEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topology = Topology((
            Luminaire("L01", "A", 1, ("Z01", "Z02")),
            Luminaire("L02", "B", 1, ("Z02",)),
        ))
        self.levels = {"low": 10, "standard": 20, "high": 50}

    def test_max_pwm_and_historical_activity_per_led(self) -> None:
        windows = [
            make_window(0, {"Z01": 10, "Z02": 50}, {"Z01": 0, "Z02": 1}),
            make_window(15, {"Z01": 10, "Z02": 10}, {"Z01": 1, "Z02": 0}),
        ]
        records = build_luminaire_decisions(windows, self.topology, 20)
        self.assertEqual(len(records), 4)
        self.assertEqual([row["rest_pwm"] for row in records], [50, 50, 10, 10])
        self.assertEqual(records[0]["zone_pwm_requests"], "Z01:10|Z02:50")
        self.assertEqual([row["observed_any_associated_activation"] for row in records], [1, 1, 1, 0])
        summary = summarize_luminaire_decisions(records, self.topology, self.levels)[0]
        self.assertEqual(summary["overall"]["windows_by_pwm"], {"10": 2, "20": 0, "50": 2})
        self.assertEqual(summary["overall"]["associated_active_windows_at_low_pwm"], 1)
        self.assertEqual(summary["overall"]["mean_rest_pwm"], 30)
        self.assertEqual(summary["overall"]["mean_pwm_difference_from_fixed_standard"], 10)
        self.assertEqual(summary["by_luminaire"]["L02"]["associated_active_windows"], 1)

    def test_low_activity_count_stays_zero_when_no_led_uses_low(self) -> None:
        window = make_window(0, {"Z01": 20, "Z02": 50}, {"Z01": 1, "Z02": 0})
        records = build_luminaire_decisions([window], self.topology, 20)
        summary = summarize_luminaire_decisions(records, self.topology, self.levels)[0]
        self.assertEqual(summary["overall"]["windows_by_pwm"]["10"], 0)
        self.assertEqual(summary["overall"]["associated_active_windows_at_low_pwm"], 0)

    def test_missing_zone_is_rejected_before_writing_led_decisions(self) -> None:
        window = make_window(0, {"Z01": 10}, {"Z01": 0})
        with self.assertRaises(ValueError):
            build_luminaire_decisions([window], self.topology, 20)
