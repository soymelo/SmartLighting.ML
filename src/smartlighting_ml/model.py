"""Treino com scikit-learn, com ou sem ajuste específico por zona.

O modelo prevê a média de ativações em 15 minutos. A chance de pelo menos
uma ativação é calculada pela distribuição de Poisson: 1 - exp(-média).
"""

from __future__ import annotations

import math
import json
from dataclasses import dataclass
from pathlib import Path

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
    use_zone: bool = True

    def features(self, row: dict) -> tuple[tuple[int, float], ...]:
        """Transforma hora, zona e histórico em entradas do modelo."""
        if self.use_zone and row["zone_id"] not in self.zones:
            raise ValueError(f"Zona desconhecida: {row['zone_id']}")
        zone_count = len(self.zones) if self.use_zone else 0
        zone_feature = ((25 + self.zones.index(row["zone_id"]), 1.0),) if self.use_zone else ()
        start_history = 1 + 24 + zone_count + 1
        return (
            (0, 1.0),
            (1 + row["local_hour"], 1.0),
            *zone_feature,
            (25 + zone_count, float(row["local_weekday"] >= 5)),
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
            "zone_feature_enabled": self.use_zone,
            "history_minutes": list(self.history_minutes),
            "feature_order": [
                "intercept",
                *(f"hour_{hour}" for hour in range(24)),
                *(f"zone_{zone}" for zone in self.zones if self.use_zone),
                "weekend",
                *(f"log1p_previous_{minutes}m_count" for minutes in self.history_minutes),
            ],
            "weights": self.weights,
            "probability_formula": "1 - exp(-predicted_count)",
        }


def fit_poisson(
    rows: list[dict], history_minutes: tuple[int, ...], *, use_zone: bool = True,
) -> PoissonModel:
    """Ajusta a regressão de Poisson; sem zona, aceita IDs inéditos na previsão."""
    if not rows or not history_minutes or any(minutes not in HISTORY_COLUMNS for minutes in history_minutes):
        raise ValueError("Treino e histórico válidos são obrigatórios.")
    if len(set(history_minutes)) != len(history_minutes):
        raise ValueError("Históricos duplicados.")
    zones = sorted({row["zone_id"] for row in rows}) if use_zone else []
    size = 1 + 24 + len(zones) + 1 + len(history_minutes)
    template = PoissonModel(zones, history_minutes, [0.0] * size, use_zone)
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
    return PoissonModel(zones, history_minutes, [float(regressor.intercept_), *map(float, regressor.coef_)], use_zone)


def load_model(path: Path) -> PoissonModel:
    """Reconstitui e confere os pesos exportados antes de fazer previsões."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("model_type") != "poisson_regression_v2":
        raise ValueError("Formato de modelo incompatível.")
    zones = data.get("zones")
    history = data.get("history_minutes")
    weights = data.get("weights")
    use_zone = data.get("zone_feature_enabled", True)
    if (not isinstance(zones, list) or any(not isinstance(zone, str) or not zone for zone in zones)
            or len(set(zones)) != len(zones) or type(use_zone) is not bool
            or (use_zone and not zones) or (not use_zone and zones)
            or not isinstance(history, list) or not history
            or any(type(minutes) is not int or minutes not in HISTORY_COLUMNS for minutes in history)
            or len(set(history)) != len(history)
            or not isinstance(weights, list)
            or any(isinstance(weight, bool) or not isinstance(weight, (int, float))
                   or not math.isfinite(weight) for weight in weights)):
        raise ValueError("Entradas ou pesos inválidos no modelo.")
    model = PoissonModel(zones, tuple(history), [float(weight) for weight in weights], use_zone)
    if (len(model.weights) != 1 + 24 + len(zones) + 1 + len(history)
            or data.get("feature_order") != model.as_dict()["feature_order"]):
        raise ValueError("Ordem ou quantidade de pesos incompatível com as entradas.")
    return model
