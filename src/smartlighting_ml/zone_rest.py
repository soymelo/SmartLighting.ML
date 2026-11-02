"""Decide o repouso de uma zona, inclusive enquanto o histórico é incompleto."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from smartlighting_ml.dimming_policy import DimmingPolicy, load_policy
from smartlighting_ml.model import PoissonModel, load_model


@dataclass(frozen=True)
class ZoneRestDecision:
    pwm: int
    source: str
    activity_probability: float | None


def decide_zone_rest(
    model: PoissonModel, policy: DimmingPolicy,
    observation: dict | None, history_minutes_available: int,
) -> ZoneRestDecision:
    """Usa o padrão até haver todo o histórico exigido pelo modelo."""
    if type(history_minutes_available) is not int or history_minutes_available < 0:
        raise ValueError("O tempo de histórico disponível deve ser um inteiro não negativo.")
    if history_minutes_available < max(model.history_minutes):
        return ZoneRestDecision(policy.standard_pwm, "insufficient_history", None)
    if observation is None:
        raise ValueError("Informe a observação quando houver histórico completo.")
    _, probability = model.predict(observation)
    return ZoneRestDecision(policy.pwm_for_probability(probability), "model", probability)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("config/dimming_policy.json"))
    parser.add_argument("--zone-id", required=True)
    parser.add_argument("--history-minutes-available", type=int, required=True)
    parser.add_argument("--hour", type=int)
    parser.add_argument("--weekday", type=int)
    parser.add_argument("--previous-30m-count", type=int)
    args = parser.parse_args()
    model = load_model(args.model)
    if model.history_minutes != (30,):
        parser.error("Este comando espera um modelo com histórico de 30 minutos.")
    if args.history_minutes_available >= 30:
        if (args.hour is None or not 0 <= args.hour <= 23
                or args.weekday is None or not 0 <= args.weekday <= 6
                or args.previous_30m_count is None or args.previous_30m_count < 0):
            parser.error("Com histórico completo, informe hora 0–23, dia 0–6 e contagem anterior não negativa.")
        observation = {
            "zone_id": args.zone_id,
            "local_hour": args.hour,
            "local_weekday": args.weekday,
            "previous_30m_count": args.previous_30m_count,
        }
    else:
        observation = None
    decision = decide_zone_rest(
        model, load_policy(args.policy), observation, args.history_minutes_available,
    )
    probability = "sem previsão" if decision.activity_probability is None else f"{decision.activity_probability:.1%}"
    print(f"Zona: {args.zone_id} | Origem: {decision.source} | Chance: {probability} | Repouso: {decision.pwm}/255")


if __name__ == "__main__":
    main()
