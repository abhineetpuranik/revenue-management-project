"""Segmentation evaluation — REQ-12 to REQ-15.

Measures how well Phase 6 K-Means customer segmentation recovers the true
segment labels embedded in the synthetic data.  Never modifies any pipeline
output.

DB-dependent steps (RFM computation, ground-truth comparison) are skipped
gracefully if the database is not available.

Outputs (evaluation/results/):
  segmentation_k_search.csv
  segmentation_vs_ground_truth.json
  segmentation_confusion_matrix.csv
  segmentation_rfm_profile.csv
  segmentation_stability.json
  segmentation_elbow_silhouette.png
  segmentation_confusion_matrix.png
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_EVAL_ROOT = Path(__file__).resolve().parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from utils import (  # noqa: E402
    PIPELINE_ROOT,
    EVAL_RANDOM_SEED,
    get_engine,
    get_gt_engine,
    save_csv,
    save_fig,
    save_json,
)

logger = logging.getLogger(__name__)


def _insert_pipeline_root() -> None:
    root = str(PIPELINE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _try_engine(getter, label):
    """Call getter(); return engine or None on failure."""
    try:
        return getter()
    except Exception as exc:
        logger.warning("%s not available (%s) — dependent steps will be skipped.", label, exc)
        return None


def run(args=None) -> None:
    """Run all segmentation evaluations and save outputs to evaluation/results/."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    _insert_pipeline_root()

    import matplotlib  # noqa: PLC0415
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    from sklearn.metrics import (  # noqa: PLC0415
        adjusted_rand_score,
        normalized_mutual_info_score,
        confusion_matrix,
    )
    from sklearn.cluster import KMeans  # noqa: PLC0415

    from segmentation.clustering import (  # noqa: PLC0415
        clustering_features,
        scale,
        k_search,
        fit_kmeans,
        recency_is_informative,
        RANDOM_STATE,
        PRODUCTION_K,
        K_MIN,
        K_MAX,
        N_INIT,
    )
    from segmentation.labeling import cluster_centroids, label_clusters  # noqa: PLC0415

    engine = _try_engine(get_engine, "App DB")
    gt_engine = _try_engine(get_gt_engine, "GT DB")

    # ------------------------------------------------------------------
    # 1. Compute RFM  (requires DB)
    # ------------------------------------------------------------------
    rfm_df = None
    if engine is not None:
        try:
            from segmentation.rfm import compute_rfm  # noqa: PLC0415
            logger.info("Computing RFM …")
            rfm_df, snapshot = compute_rfm(engine)
            logger.info("  RFM: %d customers, snapshot=%s", len(rfm_df), snapshot.date())
        except Exception as exc:
            logger.warning("RFM computation failed (%s) — using stored CSV if available.", exc)

    # Fall back to stored CSV if DB unavailable
    if rfm_df is None:
        stored_seg = PIPELINE_ROOT / "data" / "segmentation" / "customer_segments.csv"
        if stored_seg.exists():
            stored = pd.read_csv(stored_seg)
            rfm_df = stored[["customer_id", "recency_days", "frequency", "monetary"]].copy()
            logger.info("Loaded RFM from stored customer_segments.csv (%d rows)", len(rfm_df))
        else:
            logger.error("No RFM source available — segmentation eval cannot proceed.")
            save_json({"error": "No RFM data source available (DB offline and no stored CSV)"},
                      "segmentation_vs_ground_truth.json")
            return

    # ------------------------------------------------------------------
    # 2. Load ground truth  (requires GT DB)
    # ------------------------------------------------------------------
    gt_df = None
    if gt_engine is not None:
        try:
            from sqlalchemy import text  # noqa: PLC0415
            with gt_engine.connect() as conn:
                gt_df = pd.read_sql(
                    text("SELECT customer_id, true_segment FROM gt_customer_segment"), conn
                )
            logger.info("  Ground truth: %d rows", len(gt_df))
        except Exception as exc:
            logger.warning("GT query failed (%s) — ground-truth comparison skipped.", exc)

    # ------------------------------------------------------------------
    # 3. Build clustering features and scale
    # ------------------------------------------------------------------
    use_recency = recency_is_informative(rfm_df)
    feats = clustering_features(rfm_df, use_recency)
    X_scaled = scale(feats)

    # ------------------------------------------------------------------
    # 4. Re-run k_search (evaluation-only — does NOT touch stored results)
    # ------------------------------------------------------------------
    logger.info("Running k_search (k=%d…%d) …", K_MIN, K_MAX)
    ks_df = k_search(X_scaled, K_MIN, K_MAX)
    save_csv(ks_df, "segmentation_k_search.csv")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    ax1.plot(ks_df["k"], ks_df["inertia"], marker="o")
    ax1.axvline(PRODUCTION_K, color="red", linestyle="--", linewidth=1.2,
                label=f"Production k={PRODUCTION_K}")
    ax1.set_title("Elbow curve — inertia vs k")
    ax1.set_xlabel("k")
    ax1.set_ylabel("Inertia (within-cluster SSE)")
    ax1.legend()

    ax2.plot(ks_df["k"], ks_df["silhouette"], marker="o", color="green")
    ax2.axvline(PRODUCTION_K, color="red", linestyle="--", linewidth=1.2,
                label=f"Production k={PRODUCTION_K}")
    ax2.set_title("Silhouette score vs k")
    ax2.set_xlabel("k")
    ax2.set_ylabel("Silhouette score")
    ax2.legend()

    fig.suptitle("K-Means k-search results", fontsize=13)
    fig.tight_layout()
    save_fig(fig, "segmentation_elbow_silhouette.png")

    # ------------------------------------------------------------------
    # 5. Production clustering (seed = RANDOM_STATE = 42)
    # ------------------------------------------------------------------
    km = fit_kmeans(X_scaled, PRODUCTION_K)
    cluster_ids = km.labels_

    centroids = cluster_centroids(rfm_df, cluster_ids)
    label_map = label_clusters(centroids)

    rfm_df = rfm_df.copy()
    rfm_df["cluster_id"] = cluster_ids
    rfm_df["segment_label"] = rfm_df["cluster_id"].map(label_map)

    # ------------------------------------------------------------------
    # 6. Metrics vs true_segment  (skipped if no GT)
    # ------------------------------------------------------------------
    if gt_df is not None:
        eval_df = rfm_df.merge(gt_df, on="customer_id", how="inner")
        logger.info("  Matched %d customers to ground truth", len(eval_df))

        true_codes = pd.Categorical(eval_df["true_segment"]).codes
        pred_codes = pd.Categorical(eval_df["segment_label"]).codes

        ari = float(adjusted_rand_score(true_codes, pred_codes))
        nmi = float(normalized_mutual_info_score(true_codes, pred_codes))

        purity_total = 0
        for cluster_label in eval_df["segment_label"].unique():
            mask = eval_df["segment_label"] == cluster_label
            most_common = eval_df.loc[mask, "true_segment"].value_counts().iloc[0]
            purity_total += most_common
        purity = float(purity_total / len(eval_df))

        logger.info("  ARI=%.4f  NMI=%.4f  Purity=%.4f", ari, nmi, purity)

        true_labels = sorted(eval_df["true_segment"].unique())
        pred_labels = sorted(eval_df["segment_label"].unique())
        all_labels = sorted(set(true_labels) | set(pred_labels))

        cm_full = confusion_matrix(eval_df["true_segment"], eval_df["segment_label"],
                                   labels=all_labels)
        cm_full_df = pd.DataFrame(
            cm_full,
            index=[f"true_{l}" for l in all_labels],
            columns=[f"pred_{l}" for l in all_labels],
        )
        save_csv(cm_full_df.reset_index().rename(columns={"index": "label"}),
                 "segmentation_confusion_matrix.csv")

        gt_metrics = {
            "ari": round(ari, 4),
            "nmi": round(nmi, 4),
            "purity": round(purity, 4),
            "n_customers_evaluated": int(len(eval_df)),
            "true_segment_distribution": eval_df["true_segment"].value_counts().to_dict(),
            "pred_segment_distribution": eval_df["segment_label"].value_counts().to_dict(),
            "note": (
                "ARI and NMI computed on predicted cluster labels (mapped via label_clusters) "
                "vs true_segment.  Many-to-one mappings expected: K-Means uses 4 clusters and "
                "ground truth has 4 named segments but different boundaries."
            ),
        }

        # Per-segment RFM profile
        rfm_profile = (
            eval_df.groupby("segment_label", sort=True)
            .agg(
                n_customers=("customer_id", "count"),
                mean_recency=("recency_days", "mean"),
                median_recency=("recency_days", "median"),
                mean_frequency=("frequency", "mean"),
                median_frequency=("frequency", "median"),
                mean_monetary=("monetary", "mean"),
                median_monetary=("monetary", "median"),
            )
            .round(2)
            .reset_index()
        )
        save_csv(rfm_profile, "segmentation_rfm_profile.csv")

        # Confusion matrix heatmap
        fig2, ax = plt.subplots(figsize=(7, 5))
        im = ax.imshow(cm_full, aspect="auto", cmap="Blues")
        plt.colorbar(im, ax=ax, label="Count")
        ax.set_xticks(range(len(all_labels)))
        ax.set_xticklabels([f"pred\n{l}" for l in all_labels], fontsize=8)
        ax.set_yticks(range(len(all_labels)))
        ax.set_yticklabels([f"true\n{l}" for l in all_labels], fontsize=8)
        for i in range(len(all_labels)):
            for j in range(len(all_labels)):
                ax.text(j, i, str(cm_full[i, j]), ha="center", va="center",
                        color="white" if cm_full[i, j] > cm_full.max() * 0.5 else "black",
                        fontsize=9)
        ax.set_title("Segmentation confusion matrix\n(true segment vs predicted segment label)")
        fig2.tight_layout()
        save_fig(fig2, "segmentation_confusion_matrix.png")

    else:
        gt_metrics = {
            "ari": None,
            "nmi": None,
            "purity": None,
            "note": "Ground-truth DB not available — ARI/NMI/purity could not be computed.",
        }
        save_csv(pd.DataFrame({"note": ["GT DB not available"]}),
                 "segmentation_confusion_matrix.csv")
        save_csv(
            rfm_df.groupby("segment_label", sort=True)
            .agg(n_customers=("customer_id", "count"),
                 mean_recency=("recency_days", "mean"),
                 mean_frequency=("frequency", "mean"),
                 mean_monetary=("monetary", "mean"))
            .round(2).reset_index(),
            "segmentation_rfm_profile.csv",
        )
        # Placeholder confusion matrix figure
        fig2, ax = plt.subplots(figsize=(4, 3))
        ax.text(0.5, 0.5, "GT DB not available", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Segmentation confusion matrix (unavailable)")
        fig2.tight_layout()
        save_fig(fig2, "segmentation_confusion_matrix.png")

    save_json(gt_metrics, "segmentation_vs_ground_truth.json")

    # ------------------------------------------------------------------
    # 7. Stability across seeds
    # ------------------------------------------------------------------
    logger.info("Running stability check across seeds …")
    seeds = [0, 1, 2, 42, 99]
    seed_labels: dict[int, np.ndarray] = {}
    for seed in seeds:
        km_s = KMeans(n_clusters=PRODUCTION_K, n_init=N_INIT, random_state=seed).fit(X_scaled)
        seed_labels[seed] = km_s.labels_

    ari_pairs = []
    for i in range(len(seeds)):
        for j in range(i + 1, len(seeds)):
            s1, s2 = seeds[i], seeds[j]
            pair_ari = float(adjusted_rand_score(seed_labels[s1], seed_labels[s2]))
            ari_pairs.append({"seed_a": s1, "seed_b": s2, "ari": round(pair_ari, 4)})

    stability = {
        "seeds_tested": seeds,
        "pairwise_ari": ari_pairs,
        "min_ari": round(min(p["ari"] for p in ari_pairs), 4),
        "mean_ari": round(float(np.mean([p["ari"] for p in ari_pairs])), 4),
        "note": (
            "ARI=1.0 means two seeds produce identical cluster assignments (after label "
            "permutation).  Lower ARI indicates instability.  All runs are in-memory — "
            "stored pipeline outputs are never modified."
        ),
    }
    save_json(stability, "segmentation_stability.json")
    logger.info("  Stability ARI — min=%.4f  mean=%.4f", stability["min_ari"], stability["mean_ari"])

    logger.info("Segmentation evaluation complete.")


if __name__ == "__main__":
    run()
