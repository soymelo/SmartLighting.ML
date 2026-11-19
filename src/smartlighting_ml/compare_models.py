"""Compara os dois modelos gerais nas mesmas janelas de validação sintética."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartlighting_ml.dimming_policy import DimmingPolicy, load_policy
from smartlighting_ml.evaluate import calculate_metrics, load_examples, split_chronologically
from smartlighting_ml.model import fit_poisson


SCENARIOS = ("development", "persistent_activity")


def summarize_decisions(rows: list[dict], predictions: list[tuple[float, float]],
                        policy: DimmingPolicy) -> dict:
    """Conta o repouso escolhido antes de cada janela e o movimento observado depois."""
    levels = {level: {"windows": 0, "active_windows": 0}
              for level in ("low", "standard", "high")}
    pwm_total = 0
    for row, (_, probability) in zip(rows, predictions, strict=True):
        level = policy.level_for_probability(probability)
        levels[level]["windows"] += 1
        levels[level]["active_windows"] += row["next_15m_count"] > 0
        pwm_total += policy.pwm_for_probability(probability)
    return {"levels": levels, "mean_zone_pwm": pwm_total / len(rows)}


def compare_models(processed_dir: Path, policy_path: Path) -> dict:
    """Treina em 21 dias e cruza os modelos com os mesmos 7 dias seguintes."""
    datasets = {}
    for scenario in SCENARIOS:
        metadata, examples = load_examples(processed_dir / scenario)
        if (metadata["scenario_id"] != scenario or metadata["days"] != 42
                or metadata["source"] != "synthetic"):
            raise ValueError(f"Cenário de desenvolvimento inválido: {scenario}.")
        first_28, _, _ = split_chronologically(examples, metadata, 28)
        training, validation, _ = split_chronologically(first_28, metadata, 21)
        datasets[scenario] = {"metadata": metadata, "training": training,
                              "validation": validation}

    if (datasets[SCENARIOS[0]]["metadata"]["start_local"]
            != datasets[SCENARIOS[1]]["metadata"]["start_local"]):
        raise ValueError("Os cenários devem cobrir os mesmos dias de validação.")

    policy = load_policy(policy_path)
    models = {name: fit_poisson(data["training"], (30,))
              for name, data in datasets.items()}
    results = {}
    for scenario, data in datasets.items():
        validation = data["validation"]
        results[scenario] = {
            "validation_windows": len(validation),
            "active_windows": sum(row["next_15m_count"] > 0 for row in validation),
            "models": {},
        }
        for trained_on, model in models.items():
            predictions = [model.predict(row) for row in validation]
            metrics = calculate_metrics(validation, predictions)
            results[scenario]["models"][trained_on] = {
                "brier": metrics["brier"],
                "mae": metrics["mae"],
                **summarize_decisions(validation, predictions, policy),
            }
    return {
        "method": "21 dias de treino por cenário; mesmos 7 dias seguintes de validação cruzada",
        "training_days": 21,
        "validation_days": 7,
        "history_minutes": 30,
        "policy": {"low_below": policy.standard_at, "high_at": policy.high_at,
                   "pwm": {"low": policy.low_pwm, "standard": policy.standard_pwm,
                           "high": policy.high_pwm}},
        "scenario_sha256": {name: data["metadata"]["scenario_sha256"]
                            for name, data in datasets.items()},
        "final_test_used": False,
        "holdout_used": False,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--policy", type=Path, default=Path("config/dimming_policy.json"))
    parser.add_argument("--output", type=Path, default=Path("data/evaluated/model_comparison.json"))
    args = parser.parse_args()
    report = compare_models(args.processed_dir, args.policy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Avaliação sintética cruzada: 21 dias de treino e 7 de validação")
    for scenario, result in report["results"].items():
        print(f"Cenário de teste: {scenario} | {result['validation_windows']} janelas | "
              f"{result['active_windows']} ativas")
        for trained_on, scores in result["models"].items():
            low = scores["levels"]["low"]
            high = scores["levels"]["high"]
            print(f"  Treinado em {trained_on}: Brier {scores['brier']:.5f} | "
                  f"MAE {scores['mae']:.5f} | PWM {report['policy']['pwm']['low']}: {low['windows']} "
                  f"({low['active_windows']} ativas) | PWM {report['policy']['pwm']['high']}: {high['windows']} "
                  f"({high['active_windows']} ativas)")
    print(f"Relatório: {args.output}")


if __name__ == "__main__":
    main()
