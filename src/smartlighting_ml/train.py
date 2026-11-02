"""Escolhe o histórico na validação e avalia uma única vez no teste final."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartlighting_ml.evaluate import (
    calculate_metrics,
    hour_zone_predictions,
    load_examples,
    split_chronologically,
)
from smartlighting_ml.model import fit_poisson

HISTORY_CANDIDATES = ((15,), (30,), (60,), (15, 30, 60))


def train_and_evaluate(input_dir: Path, output_dir: Path) -> dict:
    """Usa dias 1-21/22-28/29-42 para treino, validação e teste."""
    metadata, examples = load_examples(input_dir)
    if metadata["days"] != 42:
        raise ValueError("Esta comparação requer 42 dias: 21 de treino, 7 de validação e 14 de teste.")
    first_28, test, _ = split_chronologically(examples, metadata, 28)
    first_21, validation, _ = split_chronologically(first_28, metadata, 21)
    validation_results = {}
    for history in HISTORY_CANDIDATES:
        model = fit_poisson(first_21, history)
        predictions = [model.predict(row) for row in validation]
        validation_results["+".join(map(str, history))] = calculate_metrics(validation, predictions)
    chosen_key = min(validation_results, key=lambda key: validation_results[key]["brier"])
    chosen_history = tuple(int(value) for value in chosen_key.split("+"))
    final_model = fit_poisson(first_28, chosen_history)
    test_predictions = [final_model.predict(row) for row in test]
    report = {
        "scenario_id": metadata["scenario_id"],
        "source": metadata["source"],
        "split_days": {"training": 21, "validation": 7, "final_test": 14},
        "split_examples": {
            "training": len(first_21), "validation": len(validation),
            "final_training": len(first_28), "final_test": len(test),
        },
        "selection_metric": "brier",
        "validation": validation_results,
        "selected_history_minutes": list(chosen_history),
        "test": {
            "zero": calculate_metrics(test, [(0.0, 0.0)] * len(test)),
            "zona_hora": calculate_metrics(test, hour_zone_predictions(first_28, test)),
            "ml_poisson": calculate_metrics(test, test_predictions),
        },
        "test_active_windows": sum(row["next_15m_count"] > 0 for row in test),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    artifact = final_model.as_dict() | {
        "scenario_id": metadata["scenario_id"],
        "scenario_sha256": metadata["scenario_sha256"],
        "training_days": 28,
        "data_source": metadata["source"],
    }
    (output_dir / "model.json").write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = train_and_evaluate(args.input_dir, args.output_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
