"""Compara, por janela de validação, limites de decisão do brilho."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import replace
from datetime import date, timedelta, timezone
from pathlib import Path

from smartlighting_ml.dimming_policy import DimmingPolicy, load_policy
from smartlighting_ml.evaluate import load_examples, split_chronologically
from smartlighting_ml.model import HISTORY_COLUMNS, PoissonModel, fit_poisson

DEFAULT_LOW_THRESHOLDS = (0.05, 0.10, 0.15)
WINDOW_COLUMNS = (
    "scenario_id", "zone_id", "prediction_at_utc", "prediction_at_local", "local_hour", "local_weekday",
    "previous_15m_count", "previous_30m_count", "previous_60m_count",
    "predicted_count", "activity_probability", "observed_next_15m_count",
    "low_below_probability", "high_at_probability", "rest_level", "rest_pwm",
    "fixed_standard_pwm",
)


def compare_thresholds(
    validation: list[dict], model: PoissonModel, policy: DimmingPolicy,
    low_thresholds: tuple[float, ...], scenario_id: str, utc_offset_hours: int,
) -> tuple[list[dict], list[dict]]:
    """Aplica os limites às mesmas previsões, sem treinar ou olhar dias futuros."""
    if not validation or not low_thresholds or len(set(low_thresholds)) != len(low_thresholds):
        raise ValueError("Informe janelas e limites baixos distintos.")
    if any(not 0 < threshold < policy.high_at for threshold in low_thresholds):
        raise ValueError("Cada limite baixo deve ficar entre 0 e o limite alto.")
    ordered = sorted(validation, key=lambda row: (row["prediction_at_utc"], row["zone_id"]))
    local_tz = timezone(timedelta(hours=utc_offset_hours))
    predictions = [(row, *model.predict(row)) for row in ordered]
    active_total = sum(row["next_15m_count"] > 0 for row in ordered)
    records = []
    summaries = []
    for threshold in low_thresholds:
        candidate = replace(policy, standard_at=threshold)
        counts = {level: {"windows": 0, "active": 0} for level in ("low", "standard", "high")}
        pwm_total = 0
        for row, predicted_count, probability in predictions:
            level = candidate.level_for_probability(probability)
            pwm = candidate.pwm_for_probability(probability)
            active = row["next_15m_count"] > 0
            counts[level]["windows"] += 1
            counts[level]["active"] += active
            pwm_total += pwm
            records.append({
                "scenario_id": scenario_id,
                "zone_id": row["zone_id"],
                "prediction_at_utc": row["prediction_at_utc"].isoformat().replace("+00:00", "Z"),
                "prediction_at_local": row["prediction_at_utc"].astimezone(local_tz).isoformat(),
                "local_hour": row["local_hour"],
                "local_weekday": row["local_weekday"],
                "previous_15m_count": row["previous_15m_count"],
                "previous_30m_count": row["previous_30m_count"],
                "previous_60m_count": row["previous_60m_count"],
                "predicted_count": predicted_count,
                "activity_probability": probability,
                "observed_next_15m_count": row["next_15m_count"],
                "low_below_probability": threshold,
                "high_at_probability": policy.high_at,
                "rest_level": level,
                "rest_pwm": pwm,
                "fixed_standard_pwm": policy.standard_pwm,
            })
        summaries.append({
            "low_below_probability": threshold,
            "high_at_probability": policy.high_at,
            "window_count": len(ordered),
            "active_window_count": active_total,
            "levels": {
                level: {
                    **counts[level],
                    "window_share": counts[level]["windows"] / len(ordered),
                    "activity_rate_within_level": (
                        counts[level]["active"] / counts[level]["windows"]
                        if counts[level]["windows"] else None
                    ),
                }
                for level in counts
            },
            "active_windows_in_low_share": counts["low"]["active"] / active_total if active_total else None,
            "mean_rest_pwm_per_zone_window": pwm_total / len(ordered),
            "fixed_standard_pwm_per_zone_window": policy.standard_pwm,
            "mean_pwm_difference_from_fixed_standard": pwm_total / len(ordered) - policy.standard_pwm,
        })
    return records, summaries


def write_validation_report(
    input_dir: Path, training_report_path: Path, policy_path: Path,
    output_dir: Path, low_thresholds: tuple[float, ...] = DEFAULT_LOW_THRESHOLDS,
) -> dict:
    """Reajusta o modelo nos dias 1–21 e avalia brilho somente nos dias 22–28."""
    metadata, examples = load_examples(input_dir)
    if metadata["scenario_id"] == "holdout" or metadata["days"] != 42:
        raise ValueError("Use apenas um cenário de desenvolvimento com 42 dias; holdout está reservado.")
    training_report = json.loads(training_report_path.read_text(encoding="utf-8"))
    history = training_report.get("history_minutes")
    if (training_report.get("scenario_id") != metadata["scenario_id"]
            or training_report.get("scenario_sha256") != metadata["scenario_sha256"]
            or training_report.get("model_scope") != "general_without_zone_identity"
            or training_report.get("training_days") != 28
            or training_report.get("validation_training_days") != 21
            or training_report.get("validation_days") != 7
            or training_report.get("final_test_used") is not False
            or training_report.get("holdout_used") is not False
            or not isinstance(history, list) or not history
            or any(type(minutes) is not int or minutes not in HISTORY_COLUMNS for minutes in history)):
        raise ValueError("Relatório de treino incompatível com os exemplos.")
    first_28, _, _ = split_chronologically(examples, metadata, 28)
    first_21, validation, _ = split_chronologically(first_28, metadata, 21)
    model = fit_poisson(first_21, tuple(history))
    policy = load_policy(policy_path)
    records, summaries = compare_thresholds(
        validation, model, policy, low_thresholds,
        metadata["scenario_id"], metadata["utc_offset_hours"],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "window_decisions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=WINDOW_COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    report = {
        "scenario_id": metadata["scenario_id"],
        "source": metadata["source"],
        "scenario_sha256": metadata["scenario_sha256"],
        "model_scope": "general_without_zone_identity",
        "training_days": 21,
        "validation_days": 7,
        "validation_start_local": (date.fromisoformat(metadata["start_local"]) + timedelta(days=21)).isoformat(),
        "validation_end_local_exclusive": (date.fromisoformat(metadata["start_local"]) + timedelta(days=28)).isoformat(),
        "final_test_used": False,
        "holdout_used": False,
        "history_minutes": history,
        "pwm_levels": {"low": policy.low_pwm, "standard": policy.standard_pwm, "high": policy.high_pwm},
        "candidates": summaries,
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--training-report", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("config/dimming_policy.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--low-threshold", type=float, action="append")
    args = parser.parse_args()
    thresholds = tuple(args.low_threshold) if args.low_threshold else DEFAULT_LOW_THRESHOLDS
    report = write_validation_report(args.input_dir, args.training_report, args.policy, args.output_dir, thresholds)
    print(f"Cenário: {report['scenario_id']} | Histórico: {report['history_minutes']} min")
    print("Limite baixo  Janelas baixas  Ativas no baixo  Janelas altas  PWM médio")
    for candidate in report["candidates"]:
        levels = candidate["levels"]
        print(
            f"{candidate['low_below_probability']:>11.0%}  "
            f"{levels['low']['windows']:>14}  {levels['low']['active']:>14}  "
            f"{levels['high']['windows']:>13}  "
            f"{candidate['mean_rest_pwm_per_zone_window']:>9.2f}"
        )
    print(f"Janelas e resumo: {args.output_dir}")


if __name__ == "__main__":
    main()
