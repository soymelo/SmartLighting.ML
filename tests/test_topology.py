import json
import tempfile
import unittest
from pathlib import Path

from smartlighting_ml.generate import load_scenario
from smartlighting_ml.topology import load_topology, rest_pwm_by_luminaire

ROOT = Path(__file__).resolve().parents[1]


class TopologyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topology = load_topology(ROOT / "config" / "maquette_topology.json")

    def test_maquette_matches_registered_zone_led_links(self) -> None:
        self.assertEqual(len(self.topology.luminaires), 10)
        self.assertEqual(self.topology.zone_ids, frozenset(f"Z{number:02}" for number in range(1, 7)))
        for scenario_name in ("development", "persistent_activity"):
            scenario = load_scenario(ROOT / "scenarios" / f"{scenario_name}.json")
            self.assertEqual(self.topology.zone_ids,
                             frozenset(sensor["zone_id"] for sensor in scenario["sensors"]))
        self.assertEqual(sum(len(item.zone_ids) for item in self.topology.luminaires), 23)
        by_id = {item.luminaire_id: item for item in self.topology.luminaires}
        self.assertEqual((by_id["L04"].device, by_id["L04"].slot, by_id["L04"].zone_ids),
                         ("A", 4, ("Z02", "Z03", "Z04")))
        self.assertEqual((by_id["L06"].device, by_id["L06"].slot, by_id["L06"].zone_ids),
                         ("B", 1, ("Z03", "Z04", "Z05")))
        self.assertEqual(by_id["L09"].zone_ids, ("Z01", "Z05", "Z06"))

    def test_shared_led_uses_highest_zone_pwm_on_both_devices(self) -> None:
        requests = {"Z01": 10, "Z02": 10, "Z03": 20, "Z04": 50, "Z05": 10, "Z06": 20}
        self.assertEqual(rest_pwm_by_luminaire(self.topology, requests), {
            "L01": 20, "L02": 10, "L03": 20, "L04": 50, "L05": 50,
            "L06": 50, "L07": 50, "L08": 20, "L09": 20, "L10": 20,
        })
        self.assertEqual(set(rest_pwm_by_luminaire(self.topology, dict.fromkeys(requests, 10)).values()), {10})

    def test_missing_extra_zone_and_invalid_pwm_are_rejected(self) -> None:
        requests = dict.fromkeys(self.topology.zone_ids, 20)
        for changed in (
            {zone: pwm for zone, pwm in requests.items() if zone != "Z06"},
            requests | {"Z99": 20},
            requests | {"Z01": True},
            requests | {"Z01": 256},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                rest_pwm_by_luminaire(self.topology, changed)

    def test_loader_rejects_duplicate_led_or_device_slot(self) -> None:
        source = json.loads((ROOT / "config" / "maquette_topology.json").read_text(encoding="utf-8"))
        for duplicate in (
            dict(source["luminaires"][0], zone_ids=["Z01", "Z06"]),
            dict(source["luminaires"][0], luminaire_id="L99"),
        ):
            data = dict(source, luminaires=[*source["luminaires"], duplicate])
            with tempfile.TemporaryDirectory(dir=ROOT) as directory:
                path = Path(directory) / "invalid.json"
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_topology(path)

    def test_another_topology_is_supported_without_code_changes(self) -> None:
        data = {
            "schema_version": 1,
            "luminaires": [
                {"luminaire_id": "RoadLight", "device": "C", "slot": 1,
                 "zone_ids": ["North", "South"]},
            ],
        }
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "other.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            topology = load_topology(path)
            self.assertEqual(rest_pwm_by_luminaire(topology, {"North": 10, "South": 50}),
                             {"RoadLight": 50})
