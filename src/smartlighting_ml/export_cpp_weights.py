"""Gera um header C++ com os pesos escolhidos para o firmware."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from smartlighting_ml.dimming_policy import load_policy
from smartlighting_ml.model import MODEL_TYPE, load_model


def render_header(model_path: Path, policy_path: Path) -> str:
    """Valida modelo e política e produz C++ determinístico."""
    source = model_path.read_bytes()
    artifact = json.loads(source)
    model = load_model(model_path)
    policy = load_policy(policy_path)
    if (artifact.get("model_type") != MODEL_TYPE
            or artifact.get("scenario_id") != "persistent_activity"
            or artifact.get("training_days") != 28
            or artifact.get("data_source") != "synthetic"
            or model.history_minutes != (30,)
            or len(model.weights) != 27):
        raise ValueError("Use o modelo geral de 30 minutos escolhido para o firmware.")

    weights = "\n".join(
        f"    {repr(weight)},  // {feature}"
        for feature, weight in zip(artifact["feature_order"], model.weights, strict=True)
    )
    source_hash = hashlib.sha256(source).hexdigest()
    policy_hash = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    return (
        "// Gerado por SmartLighting.ML; não edite os pesos manualmente.\n"
        "// Fonte: config/firmware_model.json (persistent_activity, 28 dias).\n"
        f"// SHA-256 do JSON: {source_hash}\n"
        f"// SHA-256 da política: {policy_hash}\n"
        "#pragma once\n\n"
        "namespace ActivityModelWeights {\n"
        "constexpr int WeightCount = 27;\n"
        "constexpr int InterceptIndex = 0;\n"
        "constexpr int HourStartIndex = 1;\n"
        "constexpr int WeekendIndex = 25;\n"
        "constexpr int Previous30mIndex = 26;\n\n"
        f"constexpr double StandardAt = {repr(policy.standard_at)};\n"
        f"constexpr double HighAt = {repr(policy.high_at)};\n"
        f"constexpr int LowPwm = {policy.low_pwm};\n"
        f"constexpr int StandardPwm = {policy.standard_pwm};\n"
        f"constexpr int HighPwm = {policy.high_pwm};\n\n"
        "constexpr double Values[WeightCount] = {\n"
        f"{weights}\n"
        "};\n"
        "}  // namespace ActivityModelWeights\n"
    )


def export_cpp_weights(model_path: Path, policy_path: Path, output_path: Path) -> None:
    """Grava somente o header de dados; não altera o controle dos LEDs."""
    contents = render_header(model_path, policy_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(contents, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("config/firmware_model.json"))
    parser.add_argument("--policy", type=Path, default=Path("config/dimming_policy.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_cpp_weights(args.model, args.policy, args.output)
    print(f"Header C++ gerado: {args.output}")


if __name__ == "__main__":
    main()
