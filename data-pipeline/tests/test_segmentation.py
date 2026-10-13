import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from segmentation.clustering import (choose_k, clustering_features, elbow_k,
                                     fit_kmeans, k_search, recency_is_informative, scale)
from segmentation.labeling import cluster_centroids, label_clusters


def _synthetic_rfm(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    groups = [("A", 1000, 60000, 1), ("B", 850, 30000, 2), ("C", 450, 10000, 5), ("D", 220, 4000, 40)]
    rows = []
    for g, f, m, r in groups:
        for i in range(50):
            rows.append({"customer_id": f"{g}{i}", "group": g,
                         "frequency": int(f * rng.uniform(0.95, 1.05)),
                         "monetary": m * rng.uniform(0.9, 1.1),
                         "recency_days": max(1, int(r * rng.uniform(0.5, 1.5)))})
    return pd.DataFrame(rows)


def test_recency_rule():
    df = _synthetic_rfm()
    assert recency_is_informative(df)
    assert not recency_is_informative(df.assign(recency_days=1 + df.index % 5))


def test_clustering_features_columns():
    df = _synthetic_rfm()
    assert list(clustering_features(df, True).columns) == ["log_recency", "log_frequency", "log_monetary"]
    assert list(clustering_features(df, False).columns) == ["log_frequency", "log_monetary"]


def test_k_search_finds_four_groups():
    X = scale(clustering_features(_synthetic_rfm(), use_recency=False))
    search = k_search(X, 2, 8)
    assert choose_k(search)["silhouette_k"] == 4


def test_labels_follow_rfm_order():
    df = _synthetic_rfm()
    X = scale(clustering_features(df, use_recency=False))
    km = fit_kmeans(X, 4)
    mapping = label_clusters(cluster_centroids(df, km.labels_))
    labels = pd.Series(km.labels_).map(mapping)
    expected = {"A": "high_value", "B": "regular", "C": "occasional", "D": "at_risk"}
    assert (labels.values == df["group"].map(expected).values).all()


def test_label_mapping_uses_each_label_once_for_k4():
    cents = pd.DataFrame({"cluster_id": [0, 1, 2, 3], "recency_days": [3, 1, 2, 9],
                          "frequency": [400, 1000, 800, 200], "monetary": [9e3, 6e4, 3e4, 4e3],
                          "customers": [1, 1, 1, 1]})
    m = label_clusters(cents)
    assert m == {1: "high_value", 2: "regular", 0: "occasional", 3: "at_risk"}


def test_elbow_detects_sharp_bend():
    search = pd.DataFrame({"k": [2, 3, 4, 5, 6], "inertia": [400, 300, 60, 50, 45]})
    assert elbow_k(search) == 4


def test_deterministic():
    X = scale(clustering_features(_synthetic_rfm(), use_recency=True))
    assert (fit_kmeans(X, 4).labels_ == fit_kmeans(X, 4).labels_).all()


def test_ground_truth_isolation():
    forbidden = re.compile(r"revenue_management_gt|gt_customer_segment|true_segment|"
                           r"purchase_rate|basket_mean|basket_std")
    for name in ["rfm.py", "clustering.py", "labeling.py", "run_segmentation.py"]:
        src = (PIPELINE_ROOT / "segmentation" / name).read_text(encoding="utf-8")
        hits = forbidden.findall(src)
        assert not hits, f"{name} references ground truth: {set(hits)}"
