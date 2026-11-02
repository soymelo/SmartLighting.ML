"""Regressão de Poisson pequena, determinística e sem bibliotecas externas.

O modelo prevê a média de ativações em 15 minutos. A chance de pelo menos
uma ativação é calculada pela distribuição de Poisson: 1 - exp(-média).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

HISTORY_COLUMNS = {
    15: "previous_15m_count",
    30: "previous_30m_count",
    60: "previous_60m_count",
}


@dataclass
class PoissonModel:
    zones: list[str]
    history_minutes: tuple[int, ...]
    weights: list[float]

    def features(self, row: dict) -> tuple[tuple[int, float], ...]:
        """Transforma hora, zona e histórico em entradas do modelo."""
        if row["zone_id"] not in self.zones:
            raise ValueError(f"Zona desconhecida: {row['zone_id']}")
        zone_index = self.zones.index(row["zone_id"])
        start_history = 1 + 24 + len(self.zones) + 1
        return (
            (0, 1.0),
            (1 + row["local_hour"], 1.0),
            (25 + zone_index, 1.0),
            (25 + len(self.zones), float(row["local_weekday"] >= 5)),
            *(
                (start_history + index, math.log1p(row[HISTORY_COLUMNS[minutes]]))
                for index, minutes in enumerate(self.history_minutes)
            ),
        )

    def predict(self, row: dict) -> tuple[float, float]:
        """Retorna contagem média e probabilidade de movimento."""
        score = sum(self.weights[index] * value for index, value in self.features(row))
        mean = math.exp(max(-10.0, min(5.0, score)))
        return mean, -math.expm1(-mean)

    def as_dict(self) -> dict:
        """Representação simples para inspecionar e exportar futuramente."""
        return {
            "model_type": "poisson_regression_v1",
            "zones": self.zones,
            "history_minutes": list(self.history_minutes),
            "weights": self.weights,
            "probability_formula": "1 - exp(-predicted_count)",
        }


def fit_poisson(
    rows: list[dict], history_minutes: tuple[int, ...], epochs: int = 250
) -> PoissonModel:
    """Ajusta pesos por Adam sobre a perda de Poisson, com regularização L2."""
    if not rows or not history_minutes or any(minutes not in HISTORY_COLUMNS for minutes in history_minutes):
        raise ValueError("Treino e histórico válidos são obrigatórios.")
    if len(set(history_minutes)) != len(history_minutes) or epochs < 1:
        raise ValueError("Históricos duplicados ou número de épocas inválido.")
    zones = sorted({row["zone_id"] for row in rows})
    size = 1 + 24 + len(zones) + 1 + len(history_minutes)
    weights = [0.0] * size
    weights[0] = math.log(max(0.01, sum(row["next_15m_count"] for row in rows) / len(rows)))
    model = PoissonModel(zones, history_minutes, weights)
    encoded = [(model.features(row), row["next_15m_count"]) for row in rows]
    first_moment = [0.0] * size
    second_moment = [0.0] * size
    for epoch in range(1, epochs + 1):
        gradient = [0.0] * size
        for features, target in encoded:
            score = sum(weights[index] * value for index, value in features)
            mean = math.exp(max(-10.0, min(5.0, score)))
            difference = mean - target
            for index, value in features:
                gradient[index] += difference * value
        for index in range(size):
            regularization = 0.001 * weights[index] if index else 0.0
            value = gradient[index] / len(encoded) + regularization
            first_moment[index] = 0.9 * first_moment[index] + 0.1 * value
            second_moment[index] = 0.999 * second_moment[index] + 0.001 * value * value
            corrected_first = first_moment[index] / (1 - 0.9 ** epoch)
            corrected_second = second_moment[index] / (1 - 0.999 ** epoch)
            weights[index] -= 0.05 * corrected_first / (math.sqrt(corrected_second) + 1e-8)
    return model
