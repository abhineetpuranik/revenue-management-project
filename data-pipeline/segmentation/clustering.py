from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

RANDOM_STATE: int = 42
N_INIT: int = 20
K_MIN: int = 2
K_MAX: int = 10
PRODUCTION_K: int = 4
RECENCY_MIN_RANGE_DAYS: int = 30


def recency_is_informative(rfm: pd.DataFrame) -> bool:
    rng = int(rfm["recency_days"].max() - rfm["recency_days"].min())
    return rng >= RECENCY_MIN_RANGE_DAYS


def clustering_features(rfm: pd.DataFrame, use_recency: bool) -> pd.DataFrame:
    feats = pd.DataFrame(index=rfm.index)
    if use_recency:
        feats["log_recency"] = np.log1p(rfm["recency_days"])
    feats["log_frequency"] = np.log1p(rfm["frequency"])
    feats["log_monetary"] = np.log1p(rfm["monetary"])
    return feats


def scale(features: pd.DataFrame) -> np.ndarray:
    return StandardScaler().fit_transform(features.to_numpy(dtype=float))


def fit_kmeans(X: np.ndarray, k: int) -> KMeans:
    return KMeans(n_clusters=k, n_init=N_INIT, random_state=RANDOM_STATE).fit(X)


def k_search(X: np.ndarray, k_min: int = K_MIN, k_max: int = K_MAX) -> pd.DataFrame:
    rows = []
    for k in range(k_min, k_max + 1):
        km = fit_kmeans(X, k)
        rows.append({"k": k, "inertia": float(km.inertia_),
                     "silhouette": float(silhouette_score(X, km.labels_))})
    return pd.DataFrame(rows)


def elbow_k(search: pd.DataFrame) -> int:
    inertia = search["inertia"].to_numpy()
    if len(inertia) < 3:
        return int(search["k"].iloc[0])
    second_diff = inertia[:-2] - 2 * inertia[1:-1] + inertia[2:]
    return int(search["k"].iloc[1 + int(np.argmax(second_diff))])


def choose_k(search: pd.DataFrame) -> dict:
    best = search.loc[search["silhouette"].idxmax()]
    return {"silhouette_k": int(best["k"]), "silhouette": float(best["silhouette"]),
            "elbow_k": elbow_k(search)}
