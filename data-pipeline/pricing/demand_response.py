"""
Demand response — Phase 8b.

Two-step method used for the recommendation
-------------------------------------------
1. BASELINE  D0 = Phase 5 production model's forecast for next week at the
   CURRENT price (captures trend, lags, seasonality and festivals).
2. PRICE RESPONSE  expected_demand(p) = D0 × (p / p_current) ^ β,
   β = the product's Phase 7 elasticity.

Why not sweep the price inside XGBoost directly? XGBoost is a tree ensemble:
its prediction is a step function of price, can be non-monotonic (a higher
price predicting higher demand), and is flat outside the prices it was trained
on. A revenue search over such a curve can pick artefacts. The elasticity curve
is smooth and economically consistent; XGBoost supplies the demand LEVEL.

The direct XGBoost sweep is still computed (xgb_direct_demand) as a DIAGNOSTIC
so the disagreement between the two methods can be reported — it is never used
for the recommendation.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_forecast_model():
    """Return (model, metadata) from Phase 5's saved artifact."""
    # Imported lazily: models.train_forecasting_models imports xgboost.
    from models.train_forecasting_models import load_model_metadata, load_production_model
    return load_production_model(), load_model_metadata()


def _feature_cols(model, metadata: dict) -> list[str]:
    cols = getattr(model, "feature_cols_", None) or metadata.get("feature_cols")
    if not cols:
        raise RuntimeError("Cannot determine the forecasting model's feature columns.")
    return list(cols)


def predict_rows(model, metadata: dict, rows: pd.DataFrame) -> np.ndarray:
    cols = _feature_cols(model, metadata)
    missing = [c for c in cols if c not in rows.columns]
    if missing:
        raise KeyError(f"Feature rows are missing model columns: {missing}")
    X = rows[cols].astype(float).reset_index(drop=True)
    preds = model.predict(X, rows["product_id"].reset_index(drop=True))
    return np.maximum(np.asarray(preds, dtype=float), 0.0)


def baseline_forecast(model, metadata: dict, base_rows_at_current: pd.DataFrame) -> pd.Series:
    """D0 per product (index = product_id), forecast at the current price."""
    d0 = predict_rows(model, metadata, base_rows_at_current)
    return pd.Series(d0, index=base_rows_at_current["product_id"].to_numpy(), name="baseline_demand")


def elasticity_scaled_demand(d0, price, current_price, elasticity):
    """expected_demand(p) = D0 × (p / p_current) ^ β   (vectorised)."""
    return np.asarray(d0, float) * np.power(np.asarray(price, float) / np.asarray(current_price, float),
                                            np.asarray(elasticity, float))


def xgb_direct_demand(model, metadata: dict, rows_at_prices: pd.DataFrame) -> np.ndarray:
    """DIAGNOSTIC ONLY: model prediction with the price features changed directly."""
    return predict_rows(model, metadata, rows_at_prices)
