"""Lê decisões por zona e reúne as zonas do mesmo intervalo de validação."""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from smartlighting_ml.evaluate_dimming import WINDOW_COLUMNS
from smartlighting_ml.topology import load_topology


@dataclass(frozen=True)
class ZoneDecision:
    scenario_id: str
    zone_id: str
    prediction_at_utc: datetime
    prediction_at_local: datetime
    low_below_probability: float
    high_at_probability: float
    activity_probability: float
    observed_next_15m_count: int
    rest_pwm: int


@dataclass(frozen=True)
class ZoneWindow:
    scenario_id: str
    prediction_at_utc: datetime
    prediction_at_local: datetime
    low_below_probability: float
    high_at_probability: float
    decisions: dict[str, ZoneDecision]


def load_zone_decisions(path: Path) -> list[ZoneDecision]:
    """Lê o CSV da avaliação por zona e rejeita horários ou valores inválidos."""
    decisions = []
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or set(reader.fieldnames) != set(WINDOW_COLUMNS):
            raise ValueError("Colunas do CSV de decisões por zona inválidas.")
        for line_number, row in enumerate(reader, start=2):
            try:
                utc_time = datetime.fromisoformat(row["prediction_at_utc"])
                local_time = datetime.fromisoformat(row["prediction_at_local"])
                low = float(row["low_below_probability"])
                high = float(row["high_at_probability"])
                probability = float(row["activity_probability"])
                pwm = int(row["rest_pwm"])
                observed = int(row["observed_next_15m_count"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"Valor inválido na linha {line_number} do CSV.") from error
            if (not row["scenario_id"] or not row["zone_id"]
                    or utc_time.tzinfo is None or local_time.tzinfo is None
                    or utc_time.utcoffset().total_seconds() != 0
                    or utc_time != local_time.astimezone(UTC)
                    or not all(math.isfinite(value) for value in (low, high, probability))
                    or not 0 < low < high < 1 or not 0 <= probability <= 1
                    or not 0 <= pwm <= 255 or observed < 0):
                raise ValueError(f"Decisão incoerente na linha {line_number} do CSV.")
            decisions.append(ZoneDecision(
                row["scenario_id"], row["zone_id"], utc_time.astimezone(UTC), local_time,
                low, high, probability, observed, pwm,
            ))
    if not decisions:
        raise ValueError("O CSV de decisões por zona está vazio.")
    return decisions


def group_zone_decisions(
    decisions: list[ZoneDecision], expected_zones: frozenset[str]
) -> list[ZoneWindow]:
    """Forma grupos completos por cenário, limites e horário, sem duplicatas."""
    if not decisions or not expected_zones:
        raise ValueError("Informe decisões e zonas esperadas.")
    grouped: dict[tuple[str, float, float, datetime], dict[str, ZoneDecision]] = {}
    history_by_zone_time: dict[tuple[str, datetime, str], tuple[float, int]] = {}
    for decision in decisions:
        key = (
            decision.scenario_id, decision.low_below_probability,
            decision.high_at_probability, decision.prediction_at_utc,
        )
        zones = grouped.setdefault(key, {})
        if decision.zone_id in zones:
            raise ValueError(f"Zona duplicada no mesmo intervalo: {decision.zone_id}.")
        history_key = (decision.scenario_id, decision.prediction_at_utc, decision.zone_id)
        history = (decision.activity_probability, decision.observed_next_15m_count)
        if history_key in history_by_zone_time and history_by_zone_time[history_key] != history:
            raise ValueError("Previsão ou movimento histórico difere entre os limites comparados.")
        history_by_zone_time[history_key] = history
        zones[decision.zone_id] = decision
    windows = []
    timestamps_by_candidate: dict[tuple[float, float], set[datetime]] = {}
    scenarios = set()
    for (scenario, low, high, utc_time), zones in sorted(grouped.items()):
        if set(zones) != expected_zones:
            raise ValueError(f"Zonas ausentes ou desconhecidas em {utc_time.isoformat()} para limite {low:.0%}.")
        local_times = {decision.prediction_at_local for decision in zones.values()}
        if len(local_times) != 1:
            raise ValueError("As zonas do mesmo intervalo têm horários locais diferentes.")
        scenarios.add(scenario)
        timestamps_by_candidate.setdefault((low, high), set()).add(utc_time)
        windows.append(ZoneWindow(scenario, utc_time, local_times.pop(), low, high, zones))
    if len(scenarios) != 1 or len({frozenset(times) for times in timestamps_by_candidate.values()}) != 1:
        raise ValueError("Cenários ou horários inconsistentes entre os limites comparados.")
    times = sorted(next(iter(timestamps_by_candidate.values())))
    if any(later - earlier != timedelta(minutes=15) for earlier, later in zip(times, times[1:])):
        raise ValueError("Há uma lacuna ou intervalo diferente de 15 minutos nos horários.")
    return windows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--topology", type=Path, default=Path("config/maquette_topology.json"))
    args = parser.parse_args()
    topology = load_topology(args.topology)
    windows = group_zone_decisions(load_zone_decisions(args.input), topology.zone_ids)
    candidates = sorted({(window.low_below_probability, window.high_at_probability) for window in windows})
    print(f"Cenário: {windows[0].scenario_id} | Zonas por grupo: {len(topology.zone_ids)}")
    print(f"Horários: {len(windows) // len(candidates)} | Limites: {len(candidates)} | Grupos: {len(windows)}")
    for low, high in candidates:
        print(f"Repouso baixo abaixo de {low:.0%}; alto a partir de {high:.0%}")
    example = windows[0]
    requests = ", ".join(f"{zone}={decision.rest_pwm}" for zone, decision in sorted(example.decisions.items()))
    print(f"Primeiro grupo: {example.prediction_at_local.isoformat()} | {requests}")


if __name__ == "__main__":
    main()
