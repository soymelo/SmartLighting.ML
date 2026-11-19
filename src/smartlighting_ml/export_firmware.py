"""Congela pesos e exemplos para conferir a inferência integrada ao ESP32."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartlighting_ml.dimming_policy import load_policy
from smartlighting_ml.model import load_model


REFERENCE_INPUTS = (
    (3, 1, 0), (3, 1, 3), (18, 1, 0), (19, 1, 1),
    (19, 1, 6), (19, 5, 0), (19, 5, 6), (23, 6, 2),
)


def export_firmware(model_path: Path, report_path: Path, policy_path: Path,
                    model_output: Path, reference_output: Path) -> None:
    """Confere a proveniência e registra previsões calculadas com os pesos exportados."""
    artifact = json.loads(model_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    model = load_model(model_path)
    policy = load_policy(policy_path)
    if (artifact.get("scenario_id") != "persistent_activity"
            or artifact.get("scenario_id") != report.get("scenario_id")
            or artifact.get("scenario_sha256") != report.get("scenario_sha256")
            or artifact.get("training_days") != report.get("training_days")
            or artifact.get("training_days") != 28
            or report.get("model_scope") != "general_without_zone_identity"
            or report.get("final_test_used") is not False
            or report.get("holdout_used") is not False
            or model.history_minutes != (30,)):
        raise ValueError("Modelo escolhido e relatório de treino incompatíveis.")

    cases = []
    for hour, weekday, previous_count in REFERENCE_INPUTS:
        mean, probability = model.predict({
            "local_hour": hour,
            "local_weekday": weekday,
            "previous_30m_count": previous_count,
        })
        cases.append({
            "local_hour": hour,
            "local_weekday": weekday,
            "previous_30m_count": previous_count,
            "predicted_count": mean,
            "activity_probability": probability,
            "rest_pwm": policy.pwm_for_probability(probability),
        })
    reference = {
        "model_type": artifact["model_type"],
        "scenario_id": artifact["scenario_id"],
        "scenario_sha256": artifact["scenario_sha256"],
        "pwm_levels": {"low": policy.low_pwm, "standard": policy.standard_pwm,
                       "high": policy.high_pwm},
        "probability_thresholds": {"standard_at": policy.standard_at,
                                   "high_at": policy.high_at},
        "cases": cases,
    }
    for path, contents in ((model_output, artifact), (reference_output, reference)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contents, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("models/persistent_activity/model.json"))
    parser.add_argument("--report", type=Path, default=Path("models/persistent_activity/report.json"))
    parser.add_argument("--policy", type=Path, default=Path("config/dimming_policy.json"))
    parser.add_argument("--model-output", type=Path, default=Path("config/firmware_model.json"))
    parser.add_argument("--reference-output", type=Path, default=Path("config/firmware_reference.json"))
    args = parser.parse_args()
    export_firmware(args.model, args.report, args.policy, args.model_output, args.reference_output)
    print(f"Pesos escolhidos: {args.model_output}")
    print(f"Casos de referência: {args.reference_output}")


if __name__ == "__main__":
    main()
