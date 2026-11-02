"""Compara regras simples antes de treinar o modelo de Machine Learning."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import fmean

from smartlighting_ml.generate import WINDOW_MINUTES
from smartlighting_ml.prepare import EXAMPLE_COLUMNS

ACTIVITY_THRESHOLD = 0.20


def load_examples(input_dir: Path) -> tuple[dict, list[dict]]:
    """Lê exemplos preparados e confere a origem e as colunas necessárias."""
    metadata = json.loads((input_dir / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("source") != "synthetic" or metadata.get("window_minutes") != WINDOW_MINUTES:
        raise ValueError("A avaliação espera janelas sintéticas de 15 minutos.")
    examples = []
    with (input_dir / "examples.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or set(reader.fieldnames) != set(EXAMPLE_COLUMNS):
            raise ValueError("Colunas do CSV de exemplos inválidas.")
        for row in reader:
            if row["scenario_id"] != metadata["scenario_id"] or not row["zone_id"]:
                raise ValueError("Cenário ou zona incompatível nos exemplos.")
            prediction_at = datetime.fromisoformat(row["prediction_at_utc"])
            if prediction_at.tzinfo is None:
                raise ValueError("Horário da previsão deve conter fuso horário.")
            hour = int(row["local_hour"])
            previous = int(row["previous_15m_count"])
            previous_30 = int(row["previous_30m_count"])
            previous_60 = int(row["previous_60m_count"])
            weekday = int(row["local_weekday"])
            target = int(row["next_15m_count"])
            if (not 0 <= hour <= 23 or not 0 <= weekday <= 6 or previous < 0
                    or previous_30 < previous or previous_60 < previous_30 or target < 0):
                raise ValueError("Hora ou contagens inválidas nos exemplos.")
            examples.append({
                "zone_id": row["zone_id"],
                "prediction_at_utc": prediction_at.astimezone(UTC),
                "local_hour": hour,
                "local_weekday": weekday,
                "previous_15m_count": previous,
                "previous_30m_count": previous_30,
                "previous_60m_count": previous_60,
                "next_15m_count": target,
            })
    if len(examples) != metadata["example_count"]:
        raise ValueError("Quantidade de exemplos não confere com os metadados.")
    return metadata, examples


def split_chronologically(
    examples: list[dict], metadata: dict, train_days: int
) -> tuple[list[dict], list[dict], datetime]:
    """Treina com os primeiros dias locais e testa somente nos dias seguintes."""
    days = metadata["days"]
    if not isinstance(train_days, int) or not 0 < train_days < days:
        raise ValueError("train_days deve ficar entre 1 e days - 1.")
    local_tz = timezone(timedelta(hours=metadata["utc_offset_hours"]))
    cutoff_day = date.fromisoformat(metadata["start_local"]) + timedelta(days=train_days)
    cutoff = datetime.combine(cutoff_day, time.min, local_tz).astimezone(UTC)
    train = [row for row in examples if row["prediction_at_utc"] < cutoff]
    test = [row for row in examples if row["prediction_at_utc"] >= cutoff]
    if not train or not test:
        raise ValueError("A divisão temporal deixou treino ou teste vazio.")
    return train, test, cutoff


def hour_zone_predictions(train: list[dict], test: list[dict]) -> list[tuple[float, float]]:
    """Usa médias calculadas apenas no treino para a mesma zona e hora."""
    totals: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0, 0])
    for row in train:
        group = totals[(row["zone_id"], row["local_hour"])]
        group[0] += row["next_15m_count"]
        group[1] += int(row["next_15m_count"] > 0)
        group[2] += 1
    global_count = fmean(row["next_15m_count"] for row in train)
    global_activity = fmean(row["next_15m_count"] > 0 for row in train)
    predictions = []
    for row in test:
        group = totals.get((row["zone_id"], row["local_hour"]))
        predictions.append(
            (group[0] / group[2], group[1] / group[2])
            if group else (global_count, global_activity)
        )
    return predictions


def calculate_metrics(test: list[dict], predictions: list[tuple[float, float]]) -> dict:
    """Mede erro de contagem e alertas para atividade na próxima janela."""
    if not test or len(test) != len(predictions):
        raise ValueError("Previsões e exemplos de teste devem ter o mesmo tamanho não vazio.")
    absolute_error = 0.0
    squared_error = 0.0
    brier_error = 0.0
    positives = 0
    alerts = 0
    true_alerts = 0
    for row, (predicted_count, activity_probability) in zip(test, predictions, strict=True):
        if predicted_count < 0 or not 0 <= activity_probability <= 1:
            raise ValueError("A previsão deve conter contagem não negativa e probabilidade entre 0 e 1.")
        target = row["next_15m_count"]
        active = int(target > 0)
        absolute_error += abs(predicted_count - target)
        squared_error += (predicted_count - target) ** 2
        brier_error += (activity_probability - active) ** 2
        positives += active
        alert = activity_probability >= ACTIVITY_THRESHOLD
        alerts += alert
        true_alerts += alert and active
    count = len(test)
    return {
        "mae": absolute_error / count,
        "rmse": math.sqrt(squared_error / count),
        "brier": brier_error / count,
        "recall": true_alerts / positives if positives else None,
        "precision": true_alerts / alerts if alerts else None,
        "alert_rate": alerts / count,
    }


def evaluate_dataset(input_dir: Path, train_days: int) -> dict:
    metadata, examples = load_examples(input_dir)
    train, test, cutoff = split_chronologically(examples, metadata, train_days)
    baselines = {
        "zero": [(0.0, 0.0) for _ in test],
        "zona_hora": hour_zone_predictions(train, test),
        "ultima_janela": [
            (float(row["previous_15m_count"]), float(row["previous_15m_count"] > 0))
            for row in test
        ],
    }
    return {
        "scenario_id": metadata["scenario_id"],
        "train_examples": len(train),
        "test_examples": len(test),
        "test_start_local": cutoff.astimezone(
            timezone(timedelta(hours=metadata["utc_offset_hours"]))
        ).date().isoformat(),
        "test_activity_rate": fmean(row["next_15m_count"] > 0 for row in test),
        "metrics": {
            name: calculate_metrics(test, predictions)
            for name, predictions in baselines.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, action="append", required=True)
    parser.add_argument("--train-days", type=int, default=28)
    args = parser.parse_args()
    print(f"Limiar ilustrativo para alertar atividade: {ACTIVITY_THRESHOLD:.0%}")
    for input_dir in args.input_dir:
        report = evaluate_dataset(input_dir, args.train_days)
        print(f"\nCenário: {report['scenario_id']}")
        print(
            f"Treino: {report['train_examples']} exemplos | Teste desde "
            f"{report['test_start_local']}: {report['test_examples']} exemplos | "
            f"Janelas ativas no teste: {report['test_activity_rate']:.1%}"
        )
        print("Regra           MAE    RMSE   Brier  Recall  Precisão  Alertas")
        for name, metrics in report["metrics"].items():
            recall = f"{metrics['recall']:.1%}" if metrics["recall"] is not None else "n/d"
            precision = f"{metrics['precision']:.1%}" if metrics["precision"] is not None else "n/d"
            print(
                f"{name:<15} {metrics['mae']:.3f}  {metrics['rmse']:.3f}  "
                f"{metrics['brier']:.3f}  {recall:>6}  {precision:>8}  "
                f"{metrics['alert_rate']:.1%}"
            )


if __name__ == "__main__":
    main()
