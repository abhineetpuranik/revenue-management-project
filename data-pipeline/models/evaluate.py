from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EPSILON = 1e-8


@dataclass
class ModelMetrics:
    model_name: str
    mae:  float
    rmse: float
    mape: float

    def __str__(self) -> str:
        return (
            f"{self.model_name:>20}  "
            f"MAE={self.mae:8.3f}  "
            f"RMSE={self.rmse:8.3f}  "
            f"MAPE={self.mape:6.2f}%"
        )


def compute_metrics(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray,
    model_name: str = "Model",
) -> ModelMetrics:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    if len(y_true) != len(y_pred):
        raise ValueError(
            f"y_true ({len(y_true)}) and y_pred ({len(y_pred)}) must have the same length."
        )

    errors = y_true - y_pred
    mae    = float(np.mean(np.abs(errors)))
    rmse   = float(np.sqrt(np.mean(errors ** 2)))
    mape   = float(np.mean(np.abs(errors) / (np.abs(y_true) + EPSILON)) * 100)

    return ModelMetrics(model_name=model_name, mae=mae, rmse=rmse, mape=mape)


def compare_models(
    metrics_a: ModelMetrics,
    metrics_b: ModelMetrics,
    primary_metric: str = "rmse",
) -> tuple[ModelMetrics, ModelMetrics, str]:
    val_a = getattr(metrics_a, primary_metric)
    val_b = getattr(metrics_b, primary_metric)

    if val_a <= val_b:
        winner, loser = metrics_a, metrics_b
    else:
        winner, loser = metrics_b, metrics_a

    improvement_pct = 100.0 * (getattr(loser, primary_metric) - getattr(winner, primary_metric)) \
                      / (getattr(loser, primary_metric) + EPSILON)

    rationale = (
        f"{winner.model_name} wins on {primary_metric.upper()} "
        f"({getattr(winner, primary_metric):.3f} vs "
        f"{getattr(loser, primary_metric):.3f}, "
        f"{improvement_pct:.1f}% improvement)"
    )
    return winner, loser, rationale


def evaluate_per_product(
    test_df: pd.DataFrame,
    y_pred: np.ndarray,
    model_name: str = "Model",
) -> pd.DataFrame:
    df = test_df[["product_id", "units_sold"]].copy()
    df["y_pred"] = y_pred
    df["model"]  = model_name

    def _metrics(g: pd.DataFrame) -> pd.Series:
        yt = g["units_sold"].values.astype(float)
        yp = g["y_pred"].values.astype(float)
        err = yt - yp
        return pd.Series({
            "mae":    float(np.mean(np.abs(err))),
            "rmse":   float(np.sqrt(np.mean(err ** 2))),
            "mape":   float(np.mean(np.abs(err) / (np.abs(yt) + EPSILON)) * 100),
            "n_rows": len(g),
        })

    per_product = (
        df.groupby("product_id", sort=True)
        .apply(_metrics, include_groups=False)
        .reset_index()
    )
    return per_product.sort_values("rmse", ascending=False).reset_index(drop=True)
