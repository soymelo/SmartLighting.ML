"""Gera ativações de sensores simuladas e reproduzíveis para a maquete.

Os identificadores S01... e Z01... espelham a estrutura da maquete, não seus GUIDs.
Este módulo não escreve no banco de dados da API.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import uuid
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

EVENT_COLUMNS = ("scenario_id", "event_identifier", "sensor_id", "zone_id", "occurred_at_utc")
WINDOW_MINUTES = 15


def scenario_fingerprint(scenario: dict[str, Any]) -> str:
    """Identifica os parâmetros exatos usados para gerar os eventos."""
    encoded = json.dumps(scenario, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_scenario(path: Path) -> dict[str, Any]:
    scenario = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(scenario, dict):
        raise TypeError("O cenário deve ser um objeto JSON.")

    scenario_id = scenario.get("scenario_id")
    offset = scenario.get("utc_offset_hours")
    multipliers = scenario.get("hour_multipliers")
    weekend = scenario.get("weekend_multiplier")
    variation = scenario.get("daily_variation")
    sensors = scenario.get("sensors")

    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ValueError("scenario_id é obrigatório.")
    if not isinstance(offset, int) or not -12 <= offset <= 14:
        raise ValueError("utc_offset_hours deve ser um inteiro entre -12 e 14.")
    if not isinstance(multipliers, list) or len(multipliers) != 24 or any(
        not _nonnegative_number(value) for value in multipliers
    ):
        raise ValueError("hour_multipliers deve ter 24 números não negativos.")
    if not _nonnegative_number(weekend):
        raise ValueError("weekend_multiplier deve ser não negativo.")
    if not _nonnegative_number(variation) or variation >= 1:
        raise ValueError("daily_variation deve estar entre 0 e 1 (exclusivo).")
    if not isinstance(sensors, list) or not sensors:
        raise ValueError("sensors deve conter ao menos um sensor.")

    seen: set[str] = set()
    for sensor in sensors:
        if not isinstance(sensor, dict):
            raise TypeError("Cada sensor deve ser um objeto JSON.")
        sensor_id = sensor.get("sensor_id")
        if not isinstance(sensor_id, str) or not sensor_id.strip() or sensor_id in seen:
            raise ValueError("sensor_id deve ser único e não vazio.")
        if not isinstance(sensor.get("zone_id"), str) or not sensor["zone_id"].strip():
            raise ValueError("zone_id deve ser não vazio.")
        if not _nonnegative_number(sensor.get("base_events_per_hour")):
            raise ValueError("base_events_per_hour deve ser não negativo.")
        seen.add(sensor_id)

    if "persistent_activity" in scenario:
        activity = scenario["persistent_activity"]
        if not isinstance(activity, dict):
            raise TypeError("persistent_activity deve ser um objeto JSON.")
        required = {
            "start_probability_per_window", "min_duration_windows",
            "max_duration_windows", "rate_multiplier",
        }
        if set(activity) != required:
            raise ValueError("persistent_activity deve conter somente seus quatro parâmetros obrigatórios.")
        probability = activity["start_probability_per_window"]
        minimum = activity["min_duration_windows"]
        maximum = activity["max_duration_windows"]
        multiplier = activity["rate_multiplier"]
        if not _nonnegative_number(probability) or probability > 1:
            raise ValueError("start_probability_per_window deve estar entre 0 e 1.")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 2:
            raise ValueError("min_duration_windows deve ser um inteiro de pelo menos 2.")
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < minimum:
            raise ValueError("max_duration_windows deve ser um inteiro maior ou igual ao mínimo.")
        if not _nonnegative_number(multiplier) or multiplier < 1:
            raise ValueError("rate_multiplier deve ser pelo menos 1.")
    return scenario


def _nonnegative_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _poisson(rate: float, rng: random.Random) -> int:
    """Amostra Poisson por Knuth; as taxas do cenário são pequenas."""
    if rate == 0:
        return 0
    limit = math.exp(-rate)
    product = 1.0
    count = 0
    while product > limit:
        count += 1
        product *= rng.random()
    return count - 1


def _persistent_schedule(scenario: dict[str, Any], days: int, seed: int) -> list[set[str]]:
    """Sorteia períodos por zona; este estado não é exportado ao futuro modelo."""
    activity = scenario["persistent_activity"]
    rng = random.Random(f"persistent_activity:{seed}")
    zones = sorted({sensor["zone_id"] for sensor in scenario["sensors"]})
    remaining = {zone: 0 for zone in zones}
    cooldown = {zone: False for zone in zones}
    schedule: list[set[str]] = []
    for _ in range(days * 24 * 60 // WINDOW_MINUTES):
        busy: set[str] = set()
        for zone in zones:
            if cooldown[zone]:
                cooldown[zone] = False
                continue
            if remaining[zone] == 0 and rng.random() < activity["start_probability_per_window"]:
                remaining[zone] = rng.randint(
                    activity["min_duration_windows"], activity["max_duration_windows"]
                )
            if remaining[zone] > 0:
                busy.add(zone)
                remaining[zone] -= 1
                if remaining[zone] == 0:
                    cooldown[zone] = True
        schedule.append(busy)
    return schedule


def _generate_persistent_events(
    scenario: dict[str, Any], start_local: date, days: int, seed: int
) -> list[dict[str, str]]:
    """Gera ativações em janelas de 15 minutos com períodos por zona."""
    rng = random.Random(seed)
    local_tz = timezone(timedelta(hours=scenario["utc_offset_hours"]))
    schedule = _persistent_schedule(scenario, days, seed)
    events: list[dict[str, str]] = []
    windows_per_day = 24 * 60 // WINDOW_MINUTES
    for day_index in range(days):
        local_day = start_local + timedelta(days=day_index)
        day_start = datetime.combine(local_day, time.min, tzinfo=local_tz)
        daily_factor = rng.uniform(
            1 - scenario["daily_variation"], 1 + scenario["daily_variation"]
        )
        weekend_factor = scenario["weekend_multiplier"] if local_day.weekday() >= 5 else 1.0
        for window_index in range(windows_per_day):
            window_start = day_start + timedelta(minutes=window_index * WINDOW_MINUTES)
            hour_factor = scenario["hour_multipliers"][window_start.hour]
            busy_zones = schedule[day_index * windows_per_day + window_index]
            for sensor in scenario["sensors"]:
                multiplier = (
                    scenario["persistent_activity"]["rate_multiplier"]
                    if sensor["zone_id"] in busy_zones else 1.0
                )
                hourly_rate = (
                    sensor["base_events_per_hour"] * hour_factor
                    * weekend_factor * daily_factor * multiplier
                )
                rate = hourly_rate * WINDOW_MINUTES / 60
                for event_index in range(_poisson(rate, rng)):
                    occurred_local = window_start + timedelta(
                        seconds=rng.random() * WINDOW_MINUTES * 60
                    )
                    timestamp = occurred_local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    identifier = uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{scenario['scenario_id']}/{seed}/{sensor['sensor_id']}/{timestamp}/{event_index}",
                    )
                    events.append({
                        "scenario_id": scenario["scenario_id"],
                        "event_identifier": str(identifier),
                        "sensor_id": sensor["sensor_id"],
                        "zone_id": sensor["zone_id"],
                        "occurred_at_utc": timestamp,
                    })
    events.sort(key=lambda event: (event["occurred_at_utc"], event["sensor_id"]))
    return events


def generate_events(
    scenario: dict[str, Any], start_local: date, days: int, seed: int
) -> list[dict[str, str]]:
    if days < 1:
        raise ValueError("days deve ser positivo.")
    if "persistent_activity" in scenario:
        return _generate_persistent_events(scenario, start_local, days, seed)
    rng = random.Random(seed)
    local_tz = timezone(timedelta(hours=scenario["utc_offset_hours"]))
    events: list[dict[str, str]] = []

    for day_index in range(days):
        local_day = start_local + timedelta(days=day_index)
        daily_factor = rng.uniform(
            1 - scenario["daily_variation"], 1 + scenario["daily_variation"]
        )
        weekend_factor = scenario["weekend_multiplier"] if local_day.weekday() >= 5 else 1.0
        for hour in range(24):
            hour_start = datetime.combine(local_day, time(hour), tzinfo=local_tz)
            hour_factor = scenario["hour_multipliers"][hour]
            for sensor in scenario["sensors"]:
                rate = sensor["base_events_per_hour"] * hour_factor * weekend_factor * daily_factor
                for event_index in range(_poisson(rate, rng)):
                    occurred_local = hour_start + timedelta(seconds=rng.random() * 3600)
                    occurred_utc = occurred_local.astimezone(UTC)
                    timestamp = occurred_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    identifier = uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{scenario['scenario_id']}/{seed}/{sensor['sensor_id']}/{timestamp}/{event_index}",
                    )
                    events.append(
                        {
                            "scenario_id": scenario["scenario_id"],
                            "event_identifier": str(identifier),
                            "sensor_id": sensor["sensor_id"],
                            "zone_id": sensor["zone_id"],
                            "occurred_at_utc": timestamp,
                        }
                    )

    events.sort(key=lambda event: (event["occurred_at_utc"], event["sensor_id"]))
    return events


def write_dataset(
    scenario: dict[str, Any], start_local: date, days: int, seed: int, output_dir: Path
) -> tuple[Path, Path]:
    events = generate_events(scenario, start_local, days, seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    events_path = output_dir / "sensor_events.csv"
    metadata_path = output_dir / "metadata.json"
    with events_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVENT_COLUMNS)
        writer.writeheader()
        writer.writerows(events)
    metadata = {
        "source": "synthetic",
        "scenario_id": scenario["scenario_id"],
        "scenario_sha256": scenario_fingerprint(scenario),
        "start_local": start_local.isoformat(),
        "days": days,
        "seed": seed,
        "utc_offset_hours": scenario["utc_offset_hours"],
        "sensor_count": len(scenario["sensors"]),
        "event_count": len(events),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return events_path, metadata_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--start-local", type=date.fromisoformat, required=True)
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    scenario = load_scenario(args.scenario)
    events_path, metadata_path = write_dataset(
        scenario, args.start_local, args.days, args.seed, args.output_dir
    )
    print(f"Eventos: {events_path}")
    print(f"Metadados: {metadata_path}")


if __name__ == "__main__":
    main()
