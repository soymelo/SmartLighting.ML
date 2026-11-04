"""Avalia o repouso final de cada LED após combinar suas zonas."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from smartlighting_ml.topology import Topology, load_topology, rest_pwm_by_luminaire
from smartlighting_ml.zone_windows import ZoneWindow, group_zone_decisions, load_zone_decisions

LUMINAIRE_COLUMNS = (
    "scenario_id", "prediction_at_utc", "prediction_at_local",
    "low_below_probability", "high_at_probability",
    "luminaire_id", "device", "slot", "zone_ids", "zone_pwm_requests",
    "rest_pwm", "fixed_standard_pwm",
    "observed_associated_activation_count", "observed_any_associated_activation",
)


def build_luminaire_decisions(
    windows: list[ZoneWindow], topology: Topology, fixed_standard_pwm: int,
) -> list[dict]:
    """Aplica o maior pedido de zona a cada LED de cada janela."""
    if not windows or type(fixed_standard_pwm) is not int or not 0 <= fixed_standard_pwm <= 255:
        raise ValueError("Informe janelas e PWM padrão válidos.")
    records = []
    for window in windows:
        zone_pwm = {zone: decision.rest_pwm for zone, decision in window.decisions.items()}
        targets = rest_pwm_by_luminaire(topology, zone_pwm)
        for luminaire in topology.luminaires:
            observed = sum(
                window.decisions[zone].observed_next_15m_count
                for zone in luminaire.zone_ids
            )
            records.append({
                "scenario_id": window.scenario_id,
                "prediction_at_utc": window.prediction_at_utc.isoformat().replace("+00:00", "Z"),
                "prediction_at_local": window.prediction_at_local.isoformat(),
                "low_below_probability": window.low_below_probability,
                "high_at_probability": window.high_at_probability,
                "luminaire_id": luminaire.luminaire_id,
                "device": luminaire.device,
                "slot": luminaire.slot,
                "zone_ids": "|".join(luminaire.zone_ids),
                "zone_pwm_requests": "|".join(
                    f"{zone}:{zone_pwm[zone]}" for zone in luminaire.zone_ids
                ),
                "rest_pwm": targets[luminaire.luminaire_id],
                "fixed_standard_pwm": fixed_standard_pwm,
                "observed_associated_activation_count": observed,
                "observed_any_associated_activation": int(observed > 0),
            })
    return records


def summarize_luminaire_decisions(
    records: list[dict], topology: Topology, pwm_levels: dict[str, int]
) -> list[dict]:
    """Conta níveis e ativações associadas por candidato e por LED."""
    if (not records or set(pwm_levels) != {"low", "standard", "high"}
            or len(set(pwm_levels.values())) != 3):
        raise ValueError("Não há decisões de LED para resumir.")
    by_candidate: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for record in records:
        by_candidate[(record["low_below_probability"], record["high_at_probability"])].append(record)
    result = []
    luminaire_ids = {luminaire.luminaire_id for luminaire in topology.luminaires}
    for (low, high), candidate_rows in sorted(by_candidate.items()):
        by_led: dict[str, list[dict]] = defaultdict(list)
        for row in candidate_rows:
            by_led[row["luminaire_id"]].append(row)
        if set(by_led) != luminaire_ids or len({row["fixed_standard_pwm"] for row in candidate_rows}) != 1:
            raise ValueError("LEDs ou repouso fixo incoerentes no resumo.")
        levels = sorted(pwm_levels.values())
        if any(row["rest_pwm"] not in levels for row in candidate_rows):
            raise ValueError("PWM de LED fora dos níveis configurados.")

        def summarize_rows(rows: list[dict]) -> dict:
            active = sum(row["observed_any_associated_activation"] for row in rows)
            return {
                "window_count": len(rows),
                "windows_by_pwm": {str(pwm): sum(row["rest_pwm"] == pwm for row in rows) for pwm in levels},
                "associated_active_windows": active,
                "associated_active_windows_at_low_pwm": sum(
                    row["observed_any_associated_activation"] and row["rest_pwm"] == pwm_levels["low"]
                    for row in rows
                ),
                "mean_rest_pwm": sum(row["rest_pwm"] for row in rows) / len(rows),
            }

        overall = summarize_rows(candidate_rows)
        standard = candidate_rows[0]["fixed_standard_pwm"]
        result.append({
            "low_below_probability": low,
            "high_at_probability": high,
            "fixed_standard_pwm": standard,
            "overall": overall | {"mean_pwm_difference_from_fixed_standard": overall["mean_rest_pwm"] - standard},
            "by_luminaire": {
                luminaire.luminaire_id: summarize_rows(by_led[luminaire.luminaire_id])
                for luminaire in topology.luminaires
            },
        })
    return result


def write_luminaire_report(input_dir: Path, topology_path: Path, output_dir: Path) -> dict:
    """Lê a validação por zona e grava decisões e resumo por LED."""
    source = json.loads((input_dir / "summary.json").read_text(encoding="utf-8"))
    if (source.get("source") != "synthetic" or source.get("scenario_id") == "holdout"
            or source.get("model_scope") != "general_without_zone_identity"
            or source.get("validation_days") != 7
            or source.get("final_test_used") is not False
            or source.get("holdout_used") is not False):
        raise ValueError("Use a validação do modelo geral; teste final e holdout estão reservados.")
    topology = load_topology(topology_path)
    windows = group_zone_decisions(
        load_zone_decisions(input_dir / "window_decisions.csv"), topology.zone_ids,
    )
    if windows[0].scenario_id != source["scenario_id"]:
        raise ValueError("O cenário do CSV não confere com o resumo.")
    expected_candidates = {
        (candidate["low_below_probability"], candidate["high_at_probability"])
        for candidate in source["candidates"]
    }
    actual_candidates = {
        (window.low_below_probability, window.high_at_probability) for window in windows
    }
    if expected_candidates != actual_candidates:
        raise ValueError("Os limites do CSV não conferem com o resumo.")
    for candidate in source["candidates"]:
        candidate_key = (candidate["low_below_probability"], candidate["high_at_probability"])
        group_count = sum(
            (window.low_below_probability, window.high_at_probability) == candidate_key
            for window in windows
        )
        if candidate["window_count"] != group_count * len(topology.zone_ids):
            raise ValueError("A quantidade de janelas não confere com o resumo por zona.")
    standard_pwm = source["pwm_levels"]["standard"]
    records = build_luminaire_decisions(windows, topology, standard_pwm)
    summaries = summarize_luminaire_decisions(records, topology, source["pwm_levels"])
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "luminaire_decisions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LUMINAIRE_COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    report = {
        "scenario_id": source["scenario_id"],
        "source": source["source"],
        "scenario_sha256": source["scenario_sha256"],
        "model_scope": source["model_scope"],
        "validation_start_local": source["validation_start_local"],
        "validation_end_local_exclusive": source["validation_end_local_exclusive"],
        "final_test_used": False,
        "holdout_used": False,
        "zone_count": len(topology.zone_ids),
        "luminaire_count": len(topology.luminaires),
        "candidate_count": len(summaries),
        "luminaire_decision_count": len(records),
        "pwm_levels": source["pwm_levels"],
        "candidates": summaries,
    }
    (output_dir / "luminaire_summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--topology", type=Path, default=Path("config/maquette_topology.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = write_luminaire_report(args.input_dir, args.topology, args.output_dir)
    print(f"Cenário: {report['scenario_id']} | LEDs: {report['luminaire_count']} | Decisões: {report['luminaire_decision_count']}")
    levels = report["pwm_levels"]
    print(
        f"Limite baixo  LED-janelas em {levels['low']}  em {levels['standard']}  "
        f"em {levels['high']}  Ativas no baixo  PWM médio"
    )
    for candidate in report["candidates"]:
        overall = candidate["overall"]
        counts = overall["windows_by_pwm"]
        print(
            f"{candidate['low_below_probability']:>11.0%}  "
            f"{counts[str(levels['low'])]:>17}  {counts[str(levels['standard'])]:>5}  "
            f"{counts[str(levels['high'])]:>5}  "
            f"{overall['associated_active_windows_at_low_pwm']:>12}  {overall['mean_rest_pwm']:>9.2f}"
        )
    print(f"CSV e resumo: {args.output_dir}")


if __name__ == "__main__":
    main()
