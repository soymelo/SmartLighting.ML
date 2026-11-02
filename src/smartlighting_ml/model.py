"""Treino com scikit-learn e previsão simples para futura execução no ESP32.

O modelo prevê a média de ativações em 15 minutos. A chance de pelo menos
uma ativação é calculada pela distribuição de Poisson: 1 - exp(-média).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import sklearn
from sklearn.linear_model import PoissonRegressor

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
            "model_type": "poisson_regression_v2",
            "training_library": "scikit-learn",
            "training_library_version": sklearn.__version__,
            "zones": self.zones,
            "history_minutes": list(self.history_minutes),
            "feature_order": [
                "intercept",
                *(f"hour_{hour}" for hour in range(24)),
                *(f"zone_{zone}" for zone in self.zones),
                "weekend",
                *(f"log1p_previous_{minutes}m_count" for minutes in self.history_minutes),
            ],
            "weights": self.weights,
            "probability_formula": "1 - exp(-predicted_count)",
        }


def fit_poisson(rows: list[dict], history_minutes: tuple[int, ...]) -> PoissonModel:
    """Ajusta a regressão de Poisson; preserva entradas e saída para o firmware."""
    if not rows or not history_minutes or any(minutes not in HISTORY_COLUMNS for minutes in history_minutes):
        raise ValueError("Treino e histórico válidos são obrigatórios.")
    if len(set(history_minutes)) != len(history_minutes):
        raise ValueError("Históricos duplicados.")
    zones = sorted({row["zone_id"] for row in rows})
    size = 1 + 24 + len(zones) + 1 + len(history_minutes)
    template = PoissonModel(zones, history_minutes, [0.0] * size)
    matrix = []
    for row in rows:
        values = [0.0] * (size - 1)
        for index, value in template.features(row):
            if index:
                values[index - 1] = value
        matrix.append(values)
    targets = [row["next_15m_count"] for row in rows]
    regressor = PoissonRegressor(alpha=0.001, max_iter=1000, tol=1e-8)
    regressor.fit(matrix, targets)
    return PoissonModel(zones, history_minutes, [float(regressor.intercept_), *map(float, regressor.coef_)])
