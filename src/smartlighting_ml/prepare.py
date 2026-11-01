"""Converte ativações em janelas de 15 minutos e exemplos de previsão."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from smartlighting_ml.generate import EVENT_COLUMNS, load_scenario, scenario_fingerprint


WINDOW_MINUTES = 15
WINDOW_COLUMNS = ("scenario_id", "zone_id", "window_start_utc", "activation_count")
EXAMPLE_COLUMNS = (
    "scenario_id", "zone_id", "prediction_at_utc", "local_hour", "local_weekday",
    "previous_15m_count", "previous_60m_count", "next_15m_count",
)


def read_events(path: Path, scenario: dict, metadata: dict) -> list[tuple[str, datetime]]:
    """Lê eventos e rejeita identificadores, zonas ou horários incoerentes."""
    sensors = {sensor["sensor_id"]: sensor["zone_id"] for sensor in scenario["sensors"]}
    local_tz = timezone(timedelta(hours=scenario["utc_offset_hours"]))
    start = datetime.combine(date.fromisoformat(metadata["start_local"]), time.min, local_tz).astimezone(timezone.utc)
    end = start + timedelta(days=metadata["days"])
    events: list[tuple[str, datetime]] = []
    identifiers: set[str] = set()
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or set(reader.fieldnames) != set(EVENT_COLUMNS):
            raise ValueError("Colunas do CSV de eventos inválidas.")
        for row in reader:
            sensor_id = row["sensor_id"]
            zone_id = row["zone_id"]
            identifier = row["event_identifier"]
            if sensor_id not in sensors or sensors[sensor_id] != zone_id:
                raise ValueError(f"Sensor ou zona incompatível: {sensor_id}/{zone_id}.")
            if row["scenario_id"] != scenario["scenario_id"] or not identifier or identifier in identifiers:
                raise ValueError("Cenário ou identificador de evento inválido ou duplicado.")
            occurred = datetime.fromisoformat(row["occurred_at_utc"].replace("Z", "+00:00"))
            if occurred.tzinfo is None or not start <= occurred.astimezone(timezone.utc) < end:
                raise ValueError("Evento sem fuso horário ou fora do período gerado.")
            identifiers.add(identifier)
            events.append((zone_id, occurred.astimezone(timezone.utc)))
    if len(events) != metadata["event_count"]:
        raise ValueError("A quantidade de eventos não confere com os metadados.")
    return events


def build_windows(events: list[tuple[str, datetime]], scenario: dict, metadata: dict) -> list[dict]:
    """Cria todas as janelas por zona, mesmo quando não há ativação."""
    local_tz = timezone(timedelta(hours=scenario["utc_offset_hours"]))
    start = datetime.combine(date.fromisoformat(metadata["start_local"]), time.min, local_tz).astimezone(timezone.utc)
    days = metadata["days"]
    if not isinstance(days, int) or isinstance(days, bool) or days < 1:
        raise ValueError("days deve ser positivo.")
    window = timedelta(minutes=WINDOW_MINUTES)
    windows_per_zone = days * 24 * 60 // WINDOW_MINUTES
    zones = sorted({sensor["zone_id"] for sensor in scenario["sensors"]})
    counts = {(zone, index): 0 for zone in zones for index in range(windows_per_zone)}
    for zone, occurred in events:
        index = (occurred - start) // window
        if (zone, index) not in counts:
            raise ValueError("Evento fora das zonas ou do período informado.")
        counts[zone, index] += 1
    return [
        {
            "scenario_id": scenario["scenario_id"],
            "zone_id": zone,
            "window_start_utc": (start + index * window).isoformat().replace("+00:00", "Z"),
            "activation_count": counts[zone, index],
        }
        for zone in zones for index in range(windows_per_zone)
    ]


def build_examples(windows: list[dict], scenario: dict) -> list[dict]:
    """Usa a última hora concluída para prever a janela seguinte."""
    by_zone: dict[str, list[dict]] = {}
    for row in windows:
        by_zone.setdefault(row["zone_id"], []).append(row)
    local_tz = timezone(timedelta(hours=scenario["utc_offset_hours"]))
    examples = []
    for zone, rows in sorted(by_zone.items()):
        rows.sort(key=lambda row: row["window_start_utc"])
        for index in range(4, len(rows)):
            prediction_at = datetime.fromisoformat(rows[index]["window_start_utc"].replace("Z", "+00:00"))
            local_time = prediction_at.astimezone(local_tz)
            examples.append({
                "scenario_id": scenario["scenario_id"],
                "zone_id": zone,
                "prediction_at_utc": rows[index]["window_start_utc"],
                "local_hour": local_time.hour,
                "local_weekday": local_time.weekday(),
                "previous_15m_count": rows[index - 1]["activation_count"],
                "previous_60m_count": sum(row["activation_count"] for row in rows[index - 4:index]),
                "next_15m_count": rows[index]["activation_count"],
            })
    return examples


def write_dataset(scenario: dict, input_dir: Path, output_dir: Path) -> tuple[Path, Path]:
    """Prepara CSVs e metadados a partir do período registrado pelo gerador."""
    metadata = json.loads((input_dir / "metadata.json").read_text(encoding="utf-8"))
    if (metadata.get("source") != "synthetic"
            or metadata.get("scenario_id") != scenario["scenario_id"]
            or metadata.get("scenario_sha256") != scenario_fingerprint(scenario)
            or metadata.get("utc_offset_hours") != scenario["utc_offset_hours"]
            or metadata.get("sensor_count") != len(scenario["sensors"])):
        raise ValueError("Cenário e metadados gerados não conferem.")
    events = read_events(input_dir / "sensor_events.csv", scenario, metadata)
    windows = build_windows(events, scenario, metadata)
    examples = build_examples(windows, scenario)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, columns, rows in (
        ("windows.csv", WINDOW_COLUMNS, windows),
        ("examples.csv", EXAMPLE_COLUMNS, examples),
    ):
        with (output_dir / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    summary = {
        "source": metadata["source"],
        "scenario_id": scenario["scenario_id"],
        "scenario_sha256": metadata["scenario_sha256"],
        "start_local": metadata["start_local"],
        "days": metadata["days"],
        "utc_offset_hours": scenario["utc_offset_hours"],
        "window_minutes": WINDOW_MINUTES,
        "event_count": len(events),
        "window_count": len(windows),
        "zero_window_count": sum(row["activation_count"] == 0 for row in windows),
        "example_count": len(examples),
    }
    (output_dir / "metadata.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_dir / "windows.csv", output_dir / "examples.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    windows, examples = write_dataset(load_scenario(args.scenario), args.input_dir, args.output_dir)
    print(f"Janelas: {windows}")
    print(f"Exemplos: {examples}")


if __name__ == "__main__":
    main()
