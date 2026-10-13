from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

logger = logging.getLogger(__name__)

MODEL_NAME = "XGBoost"

XGBOOST_PARAMS: dict = {
    "n_estimators":      300,
    "max_depth":         5,
    "learning_rate":     0.05,
    "subsample":         0.8,
    "colsample_bytree":  0.8,
    "min_child_weight":  3,
    "objective":         "reg:squarederror",
    "random_state":      42,
    "n_jobs":            -1,
    "verbosity":         0,
}


class DemandXGBoost:
    def __init__(self, params: dict | None = None) -> None:
        self.params        = params or XGBOOST_PARAMS
        self.model         = XGBRegressor(**self.params)
        self.product_id_map_: dict[str, int] | None = None
        self.feature_cols_: list[str] | None = None
        self._is_fitted    = False

    def _encode_product(self, product_ids: pd.Series) -> np.ndarray:
        if self.product_id_map_ is None:
            raise RuntimeError("Model not fitted - product_id_map_ is None.")
        return product_ids.map(self.product_id_map_).fillna(-1).astype(int).values

    def _build_X(
        self,
        X: pd.DataFrame,
        product_ids: pd.Series,
    ) -> np.ndarray:
        prod_encoded = self._encode_product(product_ids).reshape(-1, 1)
        return np.hstack([prod_encoded, X[self.feature_cols_].values.astype(float)])

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        train_df: pd.DataFrame,
    ) -> "DemandXGBoost":
        self.feature_cols_ = list(X_train.columns)

        all_products = sorted(train_df["product_id"].unique().tolist())
        self.product_id_map_ = {p: i for i, p in enumerate(all_products)}

        X_full = self._build_X(X_train, train_df["product_id"])
        self.model.fit(X_full, y_train.values)
        self._is_fitted = True

        logger.info(
            "XGBoost fitted on %d rows, %d features + product label.",
            len(y_train), len(self.feature_cols_),
        )
        return self

    def predict(
        self,
        X: pd.DataFrame,
        product_ids: pd.Series | None = None,
    ) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("Model is not fitted. Call fit() first.")

        if product_ids is None:
            product_ids = pd.Series(["__unknown__"] * len(X))

        X_full = self._build_X(X, product_ids)
        preds  = self.model.predict(X_full)
        return np.maximum(preds, 0.0)

    @property
    def name(self) -> str:
        return MODEL_NAME

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("XGBoost model saved to %s", path)

    @staticmethod
    def load(path: Path) -> "DemandXGBoost":
        obj = joblib.load(path)
        if not isinstance(obj, DemandXGBoost):
            raise TypeError(f"Expected DemandXGBoost, got {type(obj)}")
        return obj
