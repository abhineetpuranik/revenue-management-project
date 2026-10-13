from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MODEL_NAME = "LinearRegression"


class DemandLinearRegression:
    def __init__(self, random_state: int = 42) -> None:
        self.random_state  = random_state
        self.model         = LinearRegression()
        self.scaler        = StandardScaler()
        self.product_ids_: list[str] | None = None
        self.feature_cols_: list[str] | None = None
        self._is_fitted    = False

    def _prepare_X(
        self,
        X: pd.DataFrame,
        train_df: pd.DataFrame | None = None,
    ) -> np.ndarray:
        if train_df is not None:
            self.product_ids_  = sorted(train_df["product_id"].unique().tolist())
            self.feature_cols_ = list(X.columns)

        if train_df is not None:
            X_scaled = self.scaler.fit_transform(X.values.astype(float))
        else:
            X_scaled = self.scaler.transform(X.values.astype(float))

        return X_scaled

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        train_df: pd.DataFrame,
    ) -> "DemandLinearRegression":
        self.product_ids_  = sorted(train_df["product_id"].unique().tolist())
        self.feature_cols_ = list(X_train.columns)

        X_scaled = self.scaler.fit_transform(X_train.values.astype(float))
        dummies  = pd.get_dummies(
            train_df["product_id"].astype("category").cat.set_categories(self.product_ids_),
            drop_first=True,
        ).values.astype(float)

        X_full = np.hstack([X_scaled, dummies])
        self.model.fit(X_full, y_train.values)
        self._is_fitted = True
        logger.info(
            "LinearRegression fitted on %d rows, %d features (numeric) + %d dummies.",
            len(y_train), X_scaled.shape[1], dummies.shape[1],
        )
        return self

    def predict(
        self,
        X: pd.DataFrame,
        product_ids: pd.Series | None = None,
    ) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("Model is not fitted. Call fit() first.")

        X_scaled = self.scaler.transform(X[self.feature_cols_].values.astype(float))

        if product_ids is not None and self.product_ids_ is not None:
            dummies = pd.get_dummies(
                pd.Categorical(product_ids, categories=self.product_ids_),
                drop_first=True,
            ).values.astype(float)
            X_full = np.hstack([X_scaled, dummies])
        else:
            n_dummies = len(self.product_ids_) - 1 if self.product_ids_ else 0
            X_full = np.hstack([X_scaled, np.zeros((len(X_scaled), n_dummies))])

        preds = self.model.predict(X_full)
        return np.maximum(preds, 0.0)

    @property
    def name(self) -> str:
        return MODEL_NAME

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("LinearRegression saved to %s", path)

    @staticmethod
    def load(path: Path) -> "DemandLinearRegression":
        obj = joblib.load(path)
        if not isinstance(obj, DemandLinearRegression):
            raise TypeError(f"Expected DemandLinearRegression, got {type(obj)}")
        return obj
