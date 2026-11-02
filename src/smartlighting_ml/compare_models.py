"""Compara o modelo por zona ao geral sem usar o teste final nem o holdout."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from smartlighting_ml.dimming_policy import DimmingPolicy, load_policy
from smartlighting_ml.evaluate import calculate_metrics, load_examples, split_chronologically
from smartlighting_ml.evaluate_dimming import compare_thresholds
from smartlighting_ml.evaluate_luminaires import build_luminaire_decisions, summarize_luminaire_decisions
from smartlighting_ml.model import PoissonModel, fit_poisson
from smartlighting_ml.topology import Topology, load_topology
from smartlighting_ml.zone_windows import ZoneDecision, group_zone_decisions

HISTORY_MINUTES = (30,)


def summarize_policy(
    rows: list[dict], predictions: list[tuple[float, float]], policy: DimmingPolicy,
) -> dict:
    """Mostra o efeito do corte escolhido nas zonas usadas como inéditas."""
    counts = {level: {"windows": 0, "active": 0} for level in ("low", "standard", "high")}
    for row, (_, probability) in zip(rows, predictions, strict=True):
        level = policy.level_for_probability(probability)
        counts[level]["windows"] += 1
        counts[level]["active"] += row["next_15m_count"] > 0
    return counts


def evaluate_model(
    model: PoissonModel, validation: list[dict], policy: DimmingPolicy,
    metadata: dict, topology: Topology,
) -> dict:
    """Mede previsão e repouso da mesma janela nos níveis de zona e LED."""
    metrics = calculate_metrics(validation, [model.predict(row) for row in validation])
    decisions, zone_summary = compare_thresholds(
        validation, model, policy, (policy.standard_at,),
        metadata["scenario_id"], metadata["utc_offset_hours"],
    )
    zone_decisions = [ZoneDecision(
        row["scenario_id"], row["zone_id"],
        datetime.fromisoformat(row["prediction_at_utc"]),
        datetime.fromisoformat(row["prediction_at_local"]),
        row["low_below_probability"], row["high_at_probability"],
        row["activity_probability"], row["observed_next_15m_count"], row["rest_pwm"],
    ) for row in decisions]
    windows = group_zone_decisions(zone_decisions, topology.zone_ids)
    led_records = build_luminaire_decisions(windows, topology, policy.standard_pwm)
    led_summary = summarize_luminaire_decisions(
        led_records, topology,
        {"low": policy.low_pwm, "standard": policy.standard_pwm, "high": policy.high_pwm},
    )[0]["overall"]
    return {"prediction": metrics, "zones": zone_summary[0], "luminaires": led_summary}


def compare_models(input_dir: Path, topology_path: Path, policy_path: Path) -> dict:
    """Treina 21 dias e avalia 7; simula também uma zona totalmente inédita."""
    metadata, examples = load_examples(input_dir)
    if metadata["scenario_id"] == "holdout" or metadata["days"] != 42:
        raise ValueError("A comparação exige 42 dias de desenvolvimento; holdout está reservado.")
    first_28, _, _ = split_chronologically(examples, metadata, 28)
    training, validation, _ = split_chronologically(first_28, metadata, 21)
    topology = load_topology(topology_path)
    if {row["zone_id"] for row in examples} != topology.zone_ids:
        raise ValueError("As zonas do cenário devem corresponder às da topologia avaliada.")
    policy = load_policy(policy_path)
    specific = fit_poisson(training, HISTORY_MINUTES)
    general = fit_poisson(training, HISTORY_MINUTES, use_zone=False)
    zones = sorted(topology.zone_ids)
    held_out = {}
    unseen_predictions = {}
    for zone in zones:
        fold_training = [row for row in training if row["zone_id"] != zone]
        fold_validation = [row for row in validation if row["zone_id"] == zone]
        fold_model = fit_poisson(fold_training, HISTORY_MINUTES, use_zone=False)
        predictions = [fold_model.predict(row) for row in fold_validation]
        held_out[zone] = {
            "prediction": calculate_metrics(fold_validation, predictions),
            "policy": summarize_policy(fold_validation, predictions, policy),
        }
        unseen_predictions[zone] = fold_model
    unseen_results = [unseen_predictions[row["zone_id"]].predict(row) for row in validation]
    pooled_unseen = calculate_metrics(
        validation, unseen_results,
    )
    return {
        "scenario_id": metadata["scenario_id"],
        "source": metadata["source"],
        "scenario_sha256": metadata["scenario_sha256"],
        "training_days": 21,
        "validation_days": 7,
        "final_test_used": False,
        "holdout_used": False,
        "history_minutes": list(HISTORY_MINUTES),
        "policy_thresholds": {"low_below": policy.standard_at, "high_at": policy.high_at},
        "zone_count": len(zones),
        "specific": evaluate_model(specific, validation, policy, metadata, topology),
        "general": evaluate_model(general, validation, policy, metadata, topology),
        "unseen_zone": {
            "method": "Para cada zona, treino nas outras cinco e avalio somente essa zona nos dias de validação.",
            "pooled_prediction": pooled_unseen,
            "pooled_policy": summarize_policy(validation, unseen_results, policy),
            "by_zone": held_out,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--topology", type=Path, default=Path("config/maquette_topology.json"))
    parser.add_argument("--policy", type=Path, default=Path("config/dimming_policy.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare_models(args.input_dir, args.topology, args.policy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Cenário: {report['scenario_id']} | treino: 21 dias | validação: 7 dias")
    print("Modelo       Brier    MAE  Zonas ativas no baixo  LEDs ativos no baixo  PWM médio por LED")
    for name in ("specific", "general"):
        result = report[name]
        print(
            f"{name:<9}  {result['prediction']['brier']:.5f}  {result['prediction']['mae']:.3f}"
            f"  {result['zones']['levels']['low']['active']:>20}"
            f"  {result['luminaires']['associated_active_windows_at_low_pwm']:>19}"
            f"  {result['luminaires']['mean_rest_pwm']:>17.2f}"
        )
    print(f"Zona inédita, Brier: {report['unseen_zone']['pooled_prediction']['brier']:.5f}")
    print(
        "Zona inédita, janelas ativas no repouso baixo: "
        f"{report['unseen_zone']['pooled_policy']['low']['active']}"
    )
    print(f"Relatório: {args.output}")


if __name__ == "__main__":
    main()
