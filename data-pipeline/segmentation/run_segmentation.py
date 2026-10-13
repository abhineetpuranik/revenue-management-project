from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import silhouette_score
from sqlalchemy import text

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from etl.db_connection import get_engine
from segmentation.clustering import (PRODUCTION_K, RECENCY_MIN_RANGE_DAYS, choose_k,
                                     clustering_features, fit_kmeans, k_search,
                                     recency_is_informative, scale)
from segmentation.labeling import LABELS_BEST_TO_WORST, cluster_centroids, label_clusters
from segmentation.rfm import compute_rfm

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

OUTPUT_DIR = _PIPELINE_ROOT / "data" / "segmentation"
SEGMENT_TABLE = "customer_rfm_segment"
SUMMARY_TABLE = "segment_summary"

CREATE_SEGMENT_SQL = """
CREATE TABLE IF NOT EXISTS customer_rfm_segment (
    customer_id     VARCHAR(10)    NOT NULL,
    recency_days    INT            NOT NULL,
    frequency       INT            NOT NULL,
    monetary        DECIMAL(14,2)  NOT NULL,
    cluster_id      INT            NOT NULL,
    segment_label   VARCHAR(20)    NOT NULL,
    assigned_at     DATETIME       NOT NULL,
    CONSTRAINT pk_customer_rfm_segment PRIMARY KEY (customer_id),
    CONSTRAINT fk_rfm_segment_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    INDEX idx_rfm_segment_label (segment_label)
) ENGINE=InnoDB
"""
CREATE_SUMMARY_SQL = """
CREATE TABLE IF NOT EXISTS segment_summary (
    segment_label        VARCHAR(20)    NOT NULL,
    customer_count       INT            NOT NULL,
    share_pct            DECIMAL(6,2)   NOT NULL,
    mean_recency_days    DECIMAL(10,2)  NOT NULL,
    median_recency_days  DECIMAL(10,2)  NOT NULL,
    mean_frequency       DECIMAL(10,2)  NOT NULL,
    median_frequency     DECIMAL(10,2)  NOT NULL,
    mean_monetary        DECIMAL(14,2)  NOT NULL,
    median_monetary      DECIMAL(14,2)  NOT NULL,
    total_revenue        DECIMAL(16,2)  NOT NULL,
    revenue_share_pct    DECIMAL(6,2)   NOT NULL,
    assigned_at          DATETIME       NOT NULL,
    CONSTRAINT pk_segment_summary PRIMARY KEY (segment_label)
) ENGINE=InnoDB
"""


def _section(title: str) -> None:
    print(f"\n--- {title} ---")


def save_plots(search: pd.DataFrame, chosen: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for col, fname, title, mark in [
        ("inertia", "elbow_plot.png", "Elbow method - K-Means inertia", chosen["elbow_k"]),
        ("silhouette", "silhouette_plot.png", "Silhouette score by k", chosen["silhouette_k"]),
    ]:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(search["k"], search[col], marker="o", color="#2b6cb0")
        ax.axvline(mark, color="#c05621", linestyle="--", linewidth=1, label=f"k = {mark}")
        ax.set_xlabel("number of clusters k")
        ax.set_ylabel(col)
        ax.set_title(title)
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(out_dir / fname, dpi=120)
        plt.close(fig)


def build_summary(seg: pd.DataFrame) -> pd.DataFrame:
    total_rev = seg["monetary"].sum()
    s = (seg.groupby("segment_label")
         .agg(customer_count=("customer_id", "size"),
              mean_recency_days=("recency_days", "mean"),
              median_recency_days=("recency_days", "median"),
              mean_frequency=("frequency", "mean"),
              median_frequency=("frequency", "median"),
              mean_monetary=("monetary", "mean"),
              median_monetary=("monetary", "median"),
              total_revenue=("monetary", "sum"))
         .reindex(LABELS_BEST_TO_WORST).dropna(how="all").reset_index())
    s["customer_count"] = s["customer_count"].astype(int)
    s["share_pct"] = s["customer_count"] / s["customer_count"].sum() * 100
    s["revenue_share_pct"] = s["total_revenue"] / total_rev * 100 if total_rev else 0.0
    cols = ["segment_label", "customer_count", "share_pct", "mean_recency_days",
            "median_recency_days", "mean_frequency", "median_frequency", "mean_monetary",
            "median_monetary", "total_revenue", "revenue_share_pct"]
    return s[cols].round(2)


def save_outputs(seg: pd.DataFrame, summary: pd.DataFrame, engine) -> None:
    seg_out = seg[["customer_id", "recency_days", "frequency", "monetary", "cluster_id",
                   "segment_label", "assigned_at"]].copy()
    seg_out["monetary"] = seg_out["monetary"].round(2)
    with engine.begin() as conn:
        conn.execute(text(CREATE_SEGMENT_SQL))
        conn.execute(text(CREATE_SUMMARY_SQL))
        conn.execute(text(f"DELETE FROM {SEGMENT_TABLE}"))
        conn.execute(text(f"DELETE FROM {SUMMARY_TABLE}"))
        seg_out.to_sql(SEGMENT_TABLE, conn, if_exists="append", index=False,
                       method="multi", chunksize=1000)
        summary.to_sql(SUMMARY_TABLE, conn, if_exists="append", index=False, method="multi")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    seg_out.to_csv(OUTPUT_DIR / "customer_segments.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "segment_summary.csv", index=False)
    logger.info("Saved %d customer rows and %d segment rows.", len(seg_out), len(summary))


def get_customer_segment(customer_id: str, engine=None) -> dict:
    engine = engine or get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(f"SELECT * FROM {SEGMENT_TABLE} WHERE customer_id = :cid"),
                         conn, params={"cid": customer_id})
    if df.empty:
        raise KeyError(f"No segment for customer_id={customer_id!r}. "
                       "Run python -m segmentation.run_segmentation first.")
    return df.iloc[0].to_dict()


def get_segment_summary(engine=None) -> pd.DataFrame:
    engine = engine or get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(text(f"SELECT * FROM {SUMMARY_TABLE}"), conn)
    order = {lab: i for i, lab in enumerate(LABELS_BEST_TO_WORST)}
    return df.sort_values("segment_label", key=lambda s: s.map(order)).reset_index(drop=True)


def main() -> None:
    t0 = time.time()
    _section("Phase 6: Customer segmentation (RFM + K-Means)")
    engine = get_engine()

    rfm, snapshot = compute_rfm(engine)
    print(f"  Snapshot date        : {snapshot.date()}")
    print(f"  Customers            : {len(rfm)}")
    print(f"  Without any purchase : {int((~rfm['has_purchases']).sum())}"
          "  (kept; frequency = monetary = 0)")
    print("\n  RFM distribution")
    print(rfm[["recency_days", "frequency", "monetary"]].describe().round(2).to_string())

    _section("Is recency informative?")
    use_recency = recency_is_informative(rfm)
    r_range = int(rfm["recency_days"].max() - rfm["recency_days"].min())
    print(f"  recency range = {r_range} days (threshold {RECENCY_MIN_RANGE_DAYS})")
    print("  -> recency " + ("USED" if use_recency else
          "EXCLUDED from clustering (every customer bought recently, so it is noise); "
          "still saved, reported and used for labeling"))

    feats = clustering_features(rfm, use_recency)
    X = scale(feats)
    print(f"  clustering features: {list(feats.columns)}")

    _section("k selection (elbow + Silhouette)")
    search = k_search(X)
    chosen = choose_k(search)
    print(search.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\n  Best Silhouette at k = {chosen['silhouette_k']} ({chosen['silhouette']:.4f}); "
          f"elbow at k = {chosen['elbow_k']}")
    if chosen["silhouette_k"] != PRODUCTION_K:
        print(f"  [FLAG] Evidence favours k = {chosen['silhouette_k']}, not {PRODUCTION_K}. "
              f"Production model still uses k = {PRODUCTION_K} to map onto the four business "
              "segments.")
    save_plots(search, chosen, OUTPUT_DIR)
    print(f"  Plots: {OUTPUT_DIR / 'elbow_plot.png'}, {OUTPUT_DIR / 'silhouette_plot.png'}")

    _section(f"Production model (k = {PRODUCTION_K})")
    km = fit_kmeans(X, PRODUCTION_K)
    sil = float(silhouette_score(X, km.labels_))
    centroids = cluster_centroids(rfm, km.labels_)
    mapping = label_clusters(centroids)
    centroids["segment_label"] = centroids["cluster_id"].map(mapping)
    print(centroids.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    seg = rfm.copy()
    seg["cluster_id"] = km.labels_.astype(int)
    seg["segment_label"] = seg["cluster_id"].map(mapping)
    seg["assigned_at"] = datetime.now().replace(microsecond=0)
    summary = build_summary(seg)
    summary["assigned_at"] = seg["assigned_at"].iloc[0]

    print("\n  Segment summary")
    print(summary.drop(columns="assigned_at").to_string(index=False))

    _section("Saving")
    save_outputs(seg, summary, engine)

    alt_feats = clustering_features(rfm, not use_recency)
    alt_X = scale(alt_feats)
    alt_km = fit_kmeans(alt_X, PRODUCTION_K)
    alt_name = f"{'+'.join(alt_feats.columns)}  (silhouette {silhouette_score(alt_X, alt_km.labels_):.3f})"
    prod_name = f"{'+'.join(feats.columns)}  (silhouette {sil:.3f})  <- production"

    _section("Validation against ground truth")
    from segmentation.validate_segmentation import run_validation
    run_validation(seg, sil, alternatives={
        prod_name: seg[["customer_id", "cluster_id"]],
        alt_name: rfm[["customer_id"]].assign(cluster_id=alt_km.labels_),
    })

    _section(f"Phase 6 complete ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
