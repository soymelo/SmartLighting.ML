"""Exporta o modelo geral escolhido, sem consultar o teste final ou holdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartlighting_ml.evaluate import calculate_metrics, load_examples, split_chronologically
from smartlighting_ml.model import fit_poisson

HISTORY_MINUTES = (30,)


def train_model(input_dir: Path, output_dir: Path) -> dict:
    """Confere a validação e ajusta pesos gerais com os primeiros 28 dias."""
    metadata, examples = load_examples(input_dir)
    if metadata["scenario_id"] == "holdout" or metadata["days"] != 42:
        raise ValueError("Use um cenário de desenvolvimento com 42 dias; holdout está reservado.")
    first_28, _, _ = split_chronologically(examples, metadata, 28)
    first_21, validation, _ = split_chronologically(first_28, metadata, 21)
    validation_model = fit_poisson(first_21, HISTORY_MINUTES)
    validation_metrics = calculate_metrics(
        validation, [validation_model.predict(row) for row in validation],
    )
    model = fit_poisson(first_28, HISTORY_MINUTES)
    trained_zones = sorted({row["zone_id"] for row in first_28})
    report = {
        "scenario_id": metadata["scenario_id"],
        "source": metadata["source"],
        "scenario_sha256": metadata["scenario_sha256"],
        "model_scope": "general_without_zone_identity",
        "history_minutes": list(HISTORY_MINUTES),
        "training_days": 28,
        "validation_days": 7,
        "validation_training_days": 21,
        "training_examples": len(first_28),
        "validation_examples": len(validation),
        "trained_zone_ids_for_provenance": trained_zones,
        "validation": validation_metrics,
        "final_test_used": False,
        "holdout_used": False,
    }
    artifact = model.as_dict() | {
        "scenario_id": metadata["scenario_id"],
        "scenario_sha256": metadata["scenario_sha256"],
        "training_days": 28,
        "data_source": metadata["source"],
        "trained_zone_ids_for_provenance": trained_zones,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    (output_dir / "model.json").write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = train_model(args.input_dir, args.output_dir)
    print(
        f"Cenário: {report['scenario_id']} | ajuste geral: {report['training_days']} dias | "
        f"histórico: {report['history_minutes']} min | Brier de validação: "
        f"{report['validation']['brier']:.5f}"
    )
    print(f"Modelo e relatório: {args.output_dir}")


if __name__ == "__main__":
    main()
