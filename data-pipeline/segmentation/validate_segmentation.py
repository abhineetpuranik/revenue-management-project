from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import (adjusted_rand_score, classification_report,
                             normalized_mutual_info_score)
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from etl.db_connection import get_gt_engine
from segmentation.labeling import LABELS_BEST_TO_WORST

_GT_SQL = "SELECT customer_id, true_segment FROM gt_customer_segment"


def load_ground_truth(gt_engine=None) -> pd.DataFrame:
    gt_engine = gt_engine or get_gt_engine()
    with gt_engine.connect() as conn:
        return pd.read_sql(text(_GT_SQL), conn)


def compute_metrics(assigned: pd.DataFrame, gt: pd.DataFrame,
                    label_col: str = "segment_label", cluster_col: str = "cluster_id") -> dict:
    m = assigned.merge(gt, on="customer_id", how="inner")
    report = classification_report(m["true_segment"], m[label_col], labels=LABELS_BEST_TO_WORST,
                                   output_dict=True, zero_division=0)
    return {
        "n_customers": int(len(m)),
        "accuracy": float((m["true_segment"] == m[label_col]).mean()),
        "ari": float(adjusted_rand_score(m["true_segment"], m[cluster_col])),
        "nmi": float(normalized_mutual_info_score(m["true_segment"], m[cluster_col])),
        "per_segment": {lab: {"precision": report[lab]["precision"],
                              "recall": report[lab]["recall"],
                              "support": int(report[lab]["support"])}
                        for lab in LABELS_BEST_TO_WORST},
        "confusion": pd.crosstab(m["true_segment"], m[label_col],
                                 rownames=["true_segment"], colnames=["assigned"])
                       .reindex(index=LABELS_BEST_TO_WORST, columns=LABELS_BEST_TO_WORST,
                                fill_value=0),
    }


def run_validation(assigned: pd.DataFrame, silhouette: float,
                   alternatives: dict[str, pd.DataFrame] | None = None) -> dict:
    gt = load_ground_truth()
    met = compute_metrics(assigned, gt)

    print("\n  Confusion matrix (rows = true_segment, columns = assigned label)")
    print(met["confusion"].to_string())
    print(f"\n  Customers evaluated : {met['n_customers']}")
    print(f"  Label accuracy      : {met['accuracy'] * 100:.1f} %")
    print(f"  Adjusted Rand Index : {met['ari']:.4f}")
    print(f"  Normalized MI       : {met['nmi']:.4f}")
    print(f"  Silhouette (final)  : {silhouette:.4f}")
    print("\n  Per-segment precision / recall")
    for lab, v in met["per_segment"].items():
        print(f"    {lab:<11} precision {v['precision']:.3f}   recall {v['recall']:.3f}   n={v['support']}")

    if alternatives:
        print("\n  Feature-set comparison (ARI vs. ground truth, k = 4)")
        for name, frame in alternatives.items():
            ari = adjusted_rand_score(frame.merge(gt, on="customer_id")["true_segment"],
                                      frame.merge(gt, on="customer_id")["cluster_id"])
            print(f"    {name:<45} ARI {ari:.4f}")
    met["confusion"] = met["confusion"].to_dict()
    return met
