"""
Linear Regression baseline model — Phase 5.

Design notes
------------
- Wraps scikit-learn's LinearRegression inside a thin class so the calling
  interface mirrors xgboost_model.py exactly.  Phase 8 and Phase 10 can
  load either model through the same predict() call.
- product_id is included as a feature via one-hot encoding (pandas
  get_dummies) so the model learns a per-product intercept shift.
  This is important because different products have very different absolute
  demand levels, and the lag features alone don't capture that without
  a product indicator.
- Predictions are clipped to [0, ∞) — demand cannot be negative.
- Saved with joblib so scikit-learn can reload it without version pinning.
"""

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
    """
    Linear Regression demand forecasting wrapper.

    Attributes
    ----------
    model       : fitted sklearn LinearRegression
    scaler      : fitted StandardScaler (applied to numeric features only)
    product_ids : list of product_id values seen during fit (for one-hot alignment)
    feature_cols: list of numeric feature column names (from data_split.FEATURE_COLS)
    """

    def __init__(self, random_state: int = 42) -> None:
        self.random_state  = random_state
        self.model         = LinearRegression()
        self.scaler        = StandardScaler()
        self.product_ids_: list[str] | None = None
        self.feature_cols_: list[str] | None = None
        self._is_fitted    = False

    # ── Internal helpers ──────────────────────────────────────────────────

    def _prepare_X(
        self,
        X: pd.DataFrame,
        train_df: pd.DataFrame | None = None,
    ) -> np.ndarray:
        """
        Build the design matrix by scaling numeric features and one-hot
        encoding product_id.

        Parameters
        ----------
        X        : feature-only DataFrame (FEATURE_COLS, no product_id).
        train_df : full training DataFrame including product_id — only needed
                   during fit to discover all product_ids.  Pass None at
                   predict time; the fitted product_ids_ list is used instead.
        """
        if train_df is not None:
            # First call (fit): record product_ids and feature cols
            self.product_ids_  = sorted(train_df["product_id"].unique().tolist())
            self.feature_cols_ = list(X.columns)

        # Scale numeric features
        if train_df is not None:
            X_scaled = self.scaler.fit_transform(X.values.astype(float))
        else:
            X_scaled = self.scaler.transform(X.values.astype(float))

        # One-hot product dummies — aligned to training set categories
        # At predict time train_df is None, so we need the product_id from X
        # but X only has numeric features.  The caller must pass product_id
        # via the predict() method for alignment.
        return X_scaled

    # ── Public API ────────────────────────────────────────────────────────

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        train_df: pd.DataFrame,
    ) -> "DemandLinearRegression":
        """
        Fit the model.

        Parameters
        ----------
        X_train  : numeric feature DataFrame (FEATURE_COLS only)
        y_train  : target Series (units_sold)
        train_df : full training DataFrame — used to extract product_id for
                   one-hot encoding.
        """
        # One-hot encode product_id and concatenate with scaled features
        self.product_ids_  = sorted(train_df["product_id"].unique().tolist())
        self.feature_cols_ = list(X_train.columns)

        X_scaled = self.scaler.fit_transform(X_train.values.astype(float))
        dummies  = pd.get_dummies(
            train_df["product_id"].astype("category").cat.set_categories(self.product_ids_),
            drop_first=True,   # drop one to avoid dummy-variable trap
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
        """
        Predict demand.

        Parameters
        ----------
        X           : feature DataFrame (FEATURE_COLS).  Rows must align with
                      product_ids if supplied.
        product_ids : Series of product_id strings matching rows in X.
                      Required if the model was fitted with product dummies.

        Returns
        -------
        np.ndarray of non-negative float predictions.
        """
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
            # Fallback: zero dummies (prediction without product-level shift)
            n_dummies = len(self.product_ids_) - 1 if self.product_ids_ else 0
            X_full = np.hstack([X_scaled, np.zeros((len(X_scaled), n_dummies))])

        preds = self.model.predict(X_full)
        return np.maximum(preds, 0.0)   # demand cannot be negative

    @property
    def name(self) -> str:
        return MODEL_NAME

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        """Save the fitted model to disk with joblib."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("LinearRegression saved to %s", path)

    @staticmethod
    def load(path: Path) -> "DemandLinearRegression":
        """Load a previously saved DemandLinearRegression from disk."""
        obj = joblib.load(path)
        if not isinstance(obj, DemandLinearRegression):
            raise TypeError(f"Expected DemandLinearRegression, got {type(obj)}")
        return obj
