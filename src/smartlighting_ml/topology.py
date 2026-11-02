"""Lê vínculos zona–LED e combina pedidos de repouso por maior PWM."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Luminaire:
    luminaire_id: str
    device: str
    slot: int
    zone_ids: tuple[str, ...]


@dataclass(frozen=True)
class Topology:
    luminaires: tuple[Luminaire, ...]

    @property
    def zone_ids(self) -> frozenset[str]:
        return frozenset(zone for luminaire in self.luminaires for zone in luminaire.zone_ids)


def load_topology(path: Path) -> Topology:
    """Lê uma topologia independente dos GUIDs usados pela API."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or set(data) != {"schema_version", "luminaires"}
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or not isinstance(data["luminaires"], list) or not data["luminaires"]):
        raise ValueError("Formato ou versão da topologia inválidos.")
    luminaires = []
    ids: set[str] = set()
    slots: set[tuple[str, int]] = set()
    for item in data["luminaires"]:
        if not isinstance(item, dict) or set(item) != {"luminaire_id", "device", "slot", "zone_ids"}:
            raise ValueError("Dados de luminária inválidos.")
        identifier, device, slot, zones = (
            item["luminaire_id"], item["device"], item["slot"], item["zone_ids"]
        )
        if (not isinstance(identifier, str) or not identifier.strip()
                or not isinstance(device, str) or not device.strip()
                or type(slot) is not int or slot < 1
                or not isinstance(zones, list) or not zones
                or any(not isinstance(zone, str) or not zone.strip() for zone in zones)
                or len(zones) != len(set(zones))
                or identifier in ids or (device, slot) in slots):
            raise ValueError("ID, dispositivo, slot ou zonas da luminária inválidos ou duplicados.")
        ids.add(identifier)
        slots.add((device, slot))
        luminaires.append(Luminaire(identifier, device, slot, tuple(zones)))
    return Topology(tuple(luminaires))


def rest_pwm_by_luminaire(topology: Topology, zone_pwm: Mapping[str, int]) -> dict[str, int]:
    """Para cada LED, escolhe o maior repouso solicitado por suas zonas."""
    if not topology.luminaires or set(zone_pwm) != topology.zone_ids:
        raise ValueError("É necessário informar exatamente as zonas da topologia.")
    if any(type(pwm) is not int or not 0 <= pwm <= 255 for pwm in zone_pwm.values()):
        raise ValueError("Cada PWM deve ser inteiro entre 0 e 255.")
    return {
        luminaire.luminaire_id: max(zone_pwm[zone] for zone in luminaire.zone_ids)
        for luminaire in topology.luminaires
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", type=Path, default=Path("config/maquette_topology.json"))
    parser.add_argument("--zone-pwm", action="append", required=True, metavar="ZONA=PWM")
    args = parser.parse_args()
    try:
        zone_pwm = {}
        for assignment in args.zone_pwm:
            zone, value = assignment.split("=", 1)
            if not zone or zone in zone_pwm:
                raise ValueError("Zona vazia ou duplicada.")
            zone_pwm[zone] = int(value)
        topology = load_topology(args.topology)
        targets = rest_pwm_by_luminaire(topology, zone_pwm)
    except ValueError as error:
        parser.error(str(error))
    for luminaire in topology.luminaires:
        requests = ", ".join(f"{zone}={zone_pwm[zone]}" for zone in luminaire.zone_ids)
        print(f"{luminaire.luminaire_id} | ESP32 {luminaire.device} slot {luminaire.slot} | {requests} -> {targets[luminaire.luminaire_id]}/255")


if __name__ == "__main__":
    main()
