"""Avalia uma vez os pesos escolhidos no cenário sintético reservado."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from smartlighting_ml.dimming_policy import load_policy
from smartlighting_ml.evaluate import calculate_metrics, load_examples
from smartlighting_ml.evaluate_dimming import WINDOW_COLUMNS, compare_thresholds
from smartlighting_ml.evaluate_luminaires import (
    LUMINAIRE_COLUMNS, build_luminaire_decisions, summarize_luminaire_decisions,
)
from smartlighting_ml.generate import load_scenario, scenario_fingerprint
from smartlighting_ml.model import load_model
from smartlighting_ml.topology import load_topology
from smartlighting_ml.zone_windows import group_zone_decisions, load_zone_decisions


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def evaluate_holdout(
    scenario_path: Path, generated_dir: Path, processed_dir: Path,
    model_path: Path, policy_path: Path, topology_path: Path, output_dir: Path,
) -> dict:
    """Usa o artefato congelado; não ajusta pesos, limites ou topologia."""
    scenario = load_scenario(scenario_path)
    generated = json.loads((generated_dir / "metadata.json").read_text(encoding="utf-8"))
    metadata, examples = load_examples(processed_dir)
    if (scenario["scenario_id"] != "holdout" or metadata["scenario_id"] != "holdout"
            or metadata["source"] != "synthetic" or metadata["days"] != 42
            or metadata["scenario_sha256"] != scenario_fingerprint(scenario)
            or generated.get("source") != "synthetic"
            or generated.get("scenario_id") != "holdout"
            or generated.get("scenario_sha256") != metadata["scenario_sha256"]
            or generated.get("start_local") != metadata["start_local"]
            or generated.get("days") != metadata["days"]
            or generated.get("event_count") != metadata["event_count"]
            or type(generated.get("seed")) is not int):
        raise ValueError("Cenário, eventos e exemplos do holdout não conferem.")

    artifact = json.loads(model_path.read_text(encoding="utf-8"))
    model = load_model(model_path)
    if (artifact.get("scenario_id") != "persistent_activity"
            or artifact.get("training_days") != 28
            or artifact.get("data_source") != "synthetic"
            or model.history_minutes != (30,)):
        raise ValueError("Use os pesos gerais escolhidos antes do teste final.")
    policy = load_policy(policy_path)
    topology = load_topology(topology_path)
    if {row["zone_id"] for row in examples} != topology.zone_ids:
        raise ValueError("As zonas do holdout não correspondem à topologia informada.")

    zone_rows, zone_summaries = compare_thresholds(
        examples, model, policy, (policy.standard_at,),
        "holdout", metadata["utc_offset_hours"],
    )
    forecast_by_zone_time = {
        (row["zone_id"], row["prediction_at_utc"]):
            (row["predicted_count"], row["activity_probability"])
        for row in zone_rows
    }
    predictions = [
        forecast_by_zone_time[(row["zone_id"], row["prediction_at_utc"].isoformat().replace("+00:00", "Z"))]
        for row in examples
    ]
    calculated_metrics = calculate_metrics(examples, predictions)
    # O recall de calculate_metrics usa um corte ilustrativo de 20%, diferente
    # do corte de 25% que comanda PWM 50. Não misturamos os dois no teste final.
    metrics = {name: calculated_metrics[name] for name in ("mae", "rmse", "brier")}
    zero_metrics = calculate_metrics(examples, [(0.0, 0.0)] * len(examples))
    zero_baseline = {name: zero_metrics[name] for name in ("mae", "rmse", "brier")}

    output_dir.mkdir(parents=True, exist_ok=True)
    zone_csv = output_dir / "window_decisions.csv"
    _write_csv(zone_csv, WINDOW_COLUMNS, zone_rows)

    windows = group_zone_decisions(load_zone_decisions(zone_csv), topology.zone_ids)
    led_rows = build_luminaire_decisions(windows, topology, policy.standard_pwm)
    _write_csv(output_dir / "luminaire_decisions.csv", LUMINAIRE_COLUMNS, led_rows)
    led_summary = summarize_luminaire_decisions(
        led_rows, topology,
        {"low": policy.low_pwm, "standard": policy.standard_pwm, "high": policy.high_pwm},
    )[0]
    active_at_high = sum(
        row["observed_any_associated_activation"] and row["rest_pwm"] == policy.high_pwm
        for row in led_rows
    )
    report = {
        "scenario_id": "holdout",
        "source": "synthetic",
        "scenario_sha256": metadata["scenario_sha256"],
        "seed": generated["seed"],
        "start_local": metadata["start_local"],
        "days": metadata["days"],
        "event_count": metadata["event_count"],
        "model_type": artifact["model_type"],
        "model_training_scenario": artifact["scenario_id"],
        "model_training_days": artifact["training_days"],
        "model_file_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "policy_file_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "topology_file_sha256": hashlib.sha256(topology_path.read_bytes()).hexdigest(),
        "final_test_used": True,
        "model_retrained_on_holdout": False,
        "pwm_levels": {"low": policy.low_pwm, "standard": policy.standard_pwm,
                       "high": policy.high_pwm},
        "probability_thresholds": {"standard_at": policy.standard_at,
                                   "high_at": policy.high_at},
        "zone": {"window_count": len(zone_rows), "metrics": metrics,
                 "always_zero_baseline_metrics": zero_baseline,
                 "decisions": zone_summaries[0]},
        "luminaire": {"led_count": len(topology.luminaires),
                      "window_count": len(led_rows),
                      "decisions": led_summary,
                      "associated_active_windows_at_high_pwm": active_at_high},
        "fixed_standard": {"pwm": policy.standard_pwm,
                           "luminaire_window_count": len(led_rows),
                           "mean_rest_pwm": policy.standard_pwm},
        "energy_measured": False,
    }
    (output_dir / "final_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=Path, default=Path("scenarios/holdout.json"))
    parser.add_argument("--generated-dir", type=Path, default=Path("data/generated/holdout"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/holdout"))
    parser.add_argument("--model", type=Path, default=Path("config/firmware_model.json"))
    parser.add_argument("--policy", type=Path, default=Path("config/dimming_policy.json"))
    parser.add_argument("--topology", type=Path, default=Path("config/maquette_topology.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/evaluated/holdout"))
    args = parser.parse_args()
    report = evaluate_holdout(
        args.scenario, args.generated_dir, args.processed_dir, args.model,
        args.policy, args.topology, args.output_dir,
    )
    levels = report["luminaire"]["decisions"]["overall"]["windows_by_pwm"]
    print(f"Holdout: {report['event_count']} eventos | "
          f"{report['zone']['window_count']} janelas de zona | "
          f"{report['luminaire']['window_count']} janelas de LED")
    print(f"Brier: {report['zone']['metrics']['brier']:.5f} | "
          f"MAE: {report['zone']['metrics']['mae']:.5f}")
    pwm = report["pwm_levels"]
    print(f"LED-janelas: PWM {pwm['low']}={levels[str(pwm['low'])]}, "
          f"{pwm['standard']}={levels[str(pwm['standard'])]}, "
          f"{pwm['high']}={levels[str(pwm['high'])]}")
    print(f"Relatório: {args.output_dir / 'final_report.json'}")


if __name__ == "__main__":
    main()
