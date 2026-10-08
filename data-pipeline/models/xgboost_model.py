"""
XGBoost demand forecasting model — Phase 5.

Design notes
------------
- product_id is label-encoded (integer) so XGBoost can learn per-product
  demand levels without the dimensionality explosion of one-hot encoding
  (50 products × 155 weeks = 7 750 rows is small enough that one-hot would
  work, but label encoding is the standard XGBoost practice and is cleaner
  for the predict() interface Phase 8 will call).
- No feature scaling needed for tree-based models.
- Hyperparameters chosen conservatively to avoid overfitting on the small
  dataset while still outperforming the linear baseline:
    n_estimators   = 300   — enough trees for a dataset this size
    max_depth      = 5     — shallow trees prevent memorising per-product patterns
    learning_rate  = 0.05  — slow learning rate with more trees → better generalisation
    subsample      = 0.8   — row subsampling per tree
    colsample_bytree = 0.8 — feature subsampling per tree
    min_child_weight = 3   — prevents splits on very small groups
    random_state   = 42    — deterministic
- Saved with joblib (wraps the entire DemandXGBoost object including the
  label encoder) so Phase 8/10 can reload without re-encoding.
"""

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
    """
    XGBoost demand forecasting wrapper.

    Attributes
    ----------
    model           : fitted XGBRegressor
    product_id_map_ : dict mapping product_id string → integer label
    feature_cols_   : list of feature column names (from data_split.FEATURE_COLS)
    """

    def __init__(self, params: dict | None = None) -> None:
        self.params        = params or XGBOOST_PARAMS
        self.model         = XGBRegressor(**self.params)
        self.product_id_map_: dict[str, int] | None = None
        self.feature_cols_: list[str] | None = None
        self._is_fitted    = False

    # ── Internal helpers ──────────────────────────────────────────────────

    def _encode_product(self, product_ids: pd.Series) -> np.ndarray:
        """Map product_id strings to integer labels."""
        if self.product_id_map_ is None:
            raise RuntimeError("Model not fitted — product_id_map_ is None.")
        return product_ids.map(self.product_id_map_).fillna(-1).astype(int).values

    def _build_X(
        self,
        X: pd.DataFrame,
        product_ids: pd.Series,
    ) -> np.ndarray:
        """Prepend the label-encoded product_id column to the feature matrix."""
        prod_encoded = self._encode_product(product_ids).reshape(-1, 1)
        return np.hstack([prod_encoded, X[self.feature_cols_].values.astype(float)])

    # ── Public API ────────────────────────────────────────────────────────

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        train_df: pd.DataFrame,
    ) -> "DemandXGBoost":
        """
        Fit the XGBoost model.

        Parameters
        ----------
        X_train  : numeric feature DataFrame (FEATURE_COLS only)
        y_train  : target Series (units_sold)
        train_df : full training DataFrame including product_id column.
        """
        self.feature_cols_ = list(X_train.columns)

        # Build label encoding from all products in training set
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
        """
        Predict demand.

        Parameters
        ----------
        X           : feature DataFrame (FEATURE_COLS).
        product_ids : Series of product_id strings matching rows in X.
                      Pass None to use a zero label (unknown product).

        Returns
        -------
        np.ndarray of non-negative float predictions.
        """
        if not self._is_fitted:
            raise RuntimeError("Model is not fitted. Call fit() first.")

        if product_ids is None:
            product_ids = pd.Series(["__unknown__"] * len(X))

        X_full = self._build_X(X, product_ids)
        preds  = self.model.predict(X_full)
        return np.maximum(preds, 0.0)   # demand cannot be negative

    @property
    def name(self) -> str:
        return MODEL_NAME

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        """Save the fitted model (including product encoding) with joblib."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("XGBoost model saved to %s", path)

    @staticmethod
    def load(path: Path) -> "DemandXGBoost":
        """Load a previously saved DemandXGBoost from disk."""
        obj = joblib.load(path)
        if not isinstance(obj, DemandXGBoost):
            raise TypeError(f"Expected DemandXGBoost, got {type(obj)}")
        return obj
