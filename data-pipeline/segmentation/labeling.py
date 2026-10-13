"""
Labeling — Phase 6 (Module 3).

Maps K-Means cluster IDs to business labels using ONLY the cluster centroids
in original RFM units (never the ground truth).

Rule
----
For each cluster compute the mean recency_days, frequency and monetary.
Standardise those centroid values across clusters (z-scores) and score

    rfm_score = z(frequency) + z(monetary) − z(recency_days)

(recency is "lower is better", hence the minus). Clusters are ranked by
score, best first, and labelled in order:

    high_value → regular → occasional → at_risk

With k = 4 each label is used once. If a different k is ever used, the
ranked clusters are split into four near-equal groups in score order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LABELS_BEST_TO_WORST: list[str] = ["high_value", "regular", "occasional", "at_risk"]


def cluster_centroids(rfm: pd.DataFrame, cluster_ids: np.ndarray) -> pd.DataFrame:
    d = rfm.assign(cluster_id=cluster_ids)
    return (d.groupby("cluster_id")
            .agg(recency_days=("recency_days", "mean"),
                 frequency=("frequency", "mean"),
                 monetary=("monetary", "mean"),
                 customers=("customer_id", "size"))
            .reset_index())


def _z(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd > 0 else s * 0.0


def label_clusters(centroids: pd.DataFrame) -> dict[int, str]:
    """Return {cluster_id: label}."""
    c = centroids.copy()
    c["rfm_score"] = _z(c["frequency"]) + _z(c["monetary"]) - _z(c["recency_days"])
    c = c.sort_values("rfm_score", ascending=False).reset_index(drop=True)
    groups = np.array_split(np.arange(len(c)), len(LABELS_BEST_TO_WORST))
    mapping: dict[int, str] = {}
    for label, idx in zip(LABELS_BEST_TO_WORST, groups):
        for i in idx:
            mapping[int(c.loc[i, "cluster_id"])] = label
    return mapping
