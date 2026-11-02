"""Converte a chance prevista de atividade em brilho de repouso configurado."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DimmingPolicy:
    """Três níveis de PWM e dois limites de probabilidade independentes do ML."""

    low_pwm: int
    standard_pwm: int
    high_pwm: int
    standard_at: float
    high_at: float

    def level_for_probability(self, probability: float) -> str:
        """Escolhe o nível para a chance de ao menos uma ativação em 15 minutos."""
        if (isinstance(probability, bool) or not isinstance(probability, (int, float))
                or not math.isfinite(probability) or not 0 <= probability <= 1):
            raise ValueError("A probabilidade deve ser um número entre 0 e 1.")
        if probability >= self.high_at:
            return "high"
        if probability >= self.standard_at:
            return "standard"
        return "low"

    def pwm_for_probability(self, probability: float) -> int:
        """Retorna o valor de PWM de 8 bits escolhido para o repouso."""
        return {
            "low": self.low_pwm,
            "standard": self.standard_pwm,
            "high": self.high_pwm,
        }[self.level_for_probability(probability)]


def load_policy(path: Path) -> DimmingPolicy:
    """Lê e valida a configuração para evitar limites ou PWM incoerentes."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {
        "schema_version", "pwm_levels", "probability_thresholds"
    } or type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Formato ou versão da política de brilho inválidos.")
    levels = data["pwm_levels"]
    thresholds = data["probability_thresholds"]
    if (not isinstance(levels, dict) or set(levels) != {"low", "standard", "high"}
            or not isinstance(thresholds, dict)
            or set(thresholds) != {"standard_at", "high_at"}):
        raise ValueError("Níveis ou limites de brilho ausentes ou desconhecidos.")
    low, standard, high = (levels[name] for name in ("low", "standard", "high"))
    standard_at, high_at = (thresholds[name] for name in ("standard_at", "high_at"))
    if (any(type(value) is not int for value in (low, standard, high))
            or not 1 <= low < standard < high < 255):
        raise ValueError("Os níveis devem ser inteiros crescentes entre 1 e 254.")
    if (any(isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) for value in (standard_at, high_at))
            or not 0 < standard_at < high_at < 1):
        raise ValueError("Os limites devem ser crescentes e ficar entre 0 e 1.")
    return DimmingPolicy(low, standard, high, float(standard_at), float(high_at))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/dimming_policy.json"))
    parser.add_argument("--probability", type=float, required=True)
    args = parser.parse_args()
    policy = load_policy(args.config)
    level = policy.level_for_probability(args.probability)
    print(f"Chance de atividade: {args.probability:.1%} | Repouso: {level} | PWM: {policy.pwm_for_probability(args.probability)}/255")


if __name__ == "__main__":
    main()
