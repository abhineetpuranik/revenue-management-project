"""Elasticity evaluation — REQ-16.

Compares Phase 7 log-log OLS elasticity estimates against the true elasticity
values embedded in the synthetic data.  Never modifies any pipeline output.

Ground-truth DB step is skipped gracefully if the DB is not available.

Outputs (evaluation/results/):
  elasticity_metrics.json
  elasticity_by_category.csv
  elasticity_worst_estimates.csv
  elasticity_scatter.png
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


def run(args=None) -> None:
    """Run all elasticity evaluations and save outputs to evaluation/results/."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    _insert_pipeline_root()

    import matplotlib  # noqa: PLC0415
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415
    import scipy.stats  # noqa: PLC0415

    # ------------------------------------------------------------------
    # 1. Load estimates (always available from CSV)
    # ------------------------------------------------------------------
    est_path = PIPELINE_ROOT / "data" / "elasticity" / "product_elasticity.csv"
    if not est_path.exists():
        raise FileNotFoundError(
            f"product_elasticity.csv not found at {est_path}.\n"
            "Run Phase 7 (pricing/elasticity_model.py) first."
        )
    est_df = pd.read_csv(est_path)
    logger.info("Loaded %d elasticity estimates from %s", len(est_df), est_path)

    # ------------------------------------------------------------------
    # 2. Load ground truth  (requires GT DB)
    # ------------------------------------------------------------------
    gt_df = None
    try:
        gt_engine = get_gt_engine()
        from sqlalchemy import text  # noqa: PLC0415
        with gt_engine.connect() as conn:
            gt_df = pd.read_sql(
                text("SELECT product_id, true_elasticity FROM gt_product_elasticity"), conn
            )
        logger.info("Loaded %d ground-truth elasticities", len(gt_df))
    except Exception as exc:
        logger.warning(
            "GT DB not available (%s) — ground-truth comparison will be skipped.", exc
        )

    # ------------------------------------------------------------------
    # 3. Metrics  (only if GT available)
    # ------------------------------------------------------------------
    if gt_df is not None:
        merged = est_df.merge(gt_df, on="product_id", how="inner")
        logger.info("Matched %d products", len(merged))

        est = merged["elasticity"].values.astype(float)
        true = merged["true_elasticity"].values.astype(float)

        mae = float(np.mean(np.abs(est - true)))
        rmse = float(np.sqrt(np.mean((est - true) ** 2)))
        pearson_r, pearson_p = scipy.stats.pearsonr(est, true)
        spearman_r, spearman_p = scipy.stats.spearmanr(est, true)
        sign_agreement = float((np.sign(est) == np.sign(true)).mean())
        negative_share = float((est < 0).mean())

        metrics = {
            "n_products": int(len(merged)),
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "pearson": round(float(pearson_r), 4),
            "pearson_p": round(float(pearson_p), 6),
            "spearman": round(float(spearman_r), 4),
            "spearman_p": round(float(spearman_p), 6),
            "sign_agreement": round(sign_agreement, 4),
            "share_estimates_negative": round(negative_share, 4),
            "note": (
                "sign_agreement: share of products where sign(estimated)==sign(true_elasticity). "
                "All true elasticities are negative (synthetic data design)."
            ),
        }
        logger.info(
            "  MAE=%.4f  RMSE=%.4f  Pearson=%.4f  Spearman=%.4f  SignAgreement=%.4f",
            mae, rmse, float(pearson_r), float(spearman_r), sign_agreement,
        )

        # Per-category
        def _cat_metrics(grp: pd.DataFrame) -> pd.Series:
            e = grp["elasticity"].values.astype(float)
            t = grp["true_elasticity"].values.astype(float)
            p_r = float(scipy.stats.pearsonr(e, t)[0]) if len(e) > 2 else float("nan")
            sp_r = float(scipy.stats.spearmanr(e, t)[0]) if len(e) > 2 else float("nan")
            return pd.Series({
                "n": len(grp),
                "mae": round(float(np.mean(np.abs(e - t))), 4),
                "rmse": round(float(np.sqrt(np.mean((e - t) ** 2))), 4),
                "pearson": round(p_r, 4) if not np.isnan(p_r) else None,
                "spearman": round(sp_r, 4) if not np.isnan(sp_r) else None,
                "sign_agreement": round(float((np.sign(e) == np.sign(t)).mean()), 4),
                "mean_estimated": round(float(e.mean()), 4),
                "mean_true": round(float(t.mean()), 4),
            })

        by_cat = (
            merged.groupby("category", sort=True)
            .apply(_cat_metrics, include_groups=False)
            .reset_index()
        )
        save_csv(by_cat, "elasticity_by_category.csv")

        # Worst estimates
        merged["abs_error"] = np.abs(merged["elasticity"] - merged["true_elasticity"])
        worst = merged[merged["abs_error"] > 0.3].sort_values("abs_error", ascending=False).copy()
        worst_cols = [
            "product_id", "category", "elasticity", "true_elasticity", "abs_error",
            "r_squared", "n_obs", "reliable_flag", "unreliable_reasons",
            "std_error", "ci_low", "ci_high",
        ]
        worst_cols_present = [c for c in worst_cols if c in worst.columns]
        save_csv(worst[worst_cols_present], "elasticity_worst_estimates.csv")
        logger.info("  Worst estimates (|error|>0.3): %d products", len(worst))

        # Scatter figure
        categories = sorted(merged["category"].unique())
        cmap = plt.cm.get_cmap("tab10", len(categories))
        cat_color = {cat: cmap(i) for i, cat in enumerate(categories)}

        fig, ax = plt.subplots(figsize=(8, 6))
        for cat in categories:
            mask = merged["category"] == cat
            ax.scatter(
                merged.loc[mask, "true_elasticity"],
                merged.loc[mask, "elasticity"],
                c=[cat_color[cat]], label=cat, alpha=0.75, s=50,
            )

        lims = [
            min(merged["true_elasticity"].min(), merged["elasticity"].min()) - 0.1,
            max(merged["true_elasticity"].max(), merged["elasticity"].max()) + 0.1,
        ]
        ax.plot(lims, lims, "k--", linewidth=1.2, label="y = x (perfect estimate)")
        ax.set_xlim(lims)
        ax.set_ylim(lims)

        top5_worst = merged.nlargest(5, "abs_error")
        for _, row in top5_worst.iterrows():
            ax.annotate(
                row["product_id"],
                (row["true_elasticity"], row["elasticity"]),
                textcoords="offset points", xytext=(5, 5), fontsize=7, color="red",
            )

        ax.set_xlabel("True elasticity")
        ax.set_ylabel("Estimated elasticity")
        ax.set_title(
            f"Elasticity: estimated vs true  "
            f"(Pearson r={float(pearson_r):.3f}, Spearman ρ={float(spearman_r):.3f})"
        )
        ax.legend(fontsize=8, loc="upper left")
        fig.tight_layout()
        save_fig(fig, "elasticity_scatter.png")

    else:
        # GT not available — save estimate-only stats
        est_vals = est_df["elasticity"].values.astype(float)
        metrics = {
            "n_products": int(len(est_df)),
            "mae": None,
            "rmse": None,
            "pearson": None,
            "spearman": None,
            "sign_agreement": None,
            "share_estimates_negative": round(float((est_vals < 0).mean()), 4),
            "mean_estimated_elasticity": round(float(est_vals.mean()), 4),
            "note": "GT DB not available — comparison metrics could not be computed.",
        }
        save_csv(pd.DataFrame({"note": ["GT DB not available"]}), "elasticity_by_category.csv")
        save_csv(pd.DataFrame({"note": ["GT DB not available"]}), "elasticity_worst_estimates.csv")

        # Scatter of estimates only (no true values)
        fig, ax = plt.subplots(figsize=(8, 5))
        if "category" in est_df.columns:
            for cat in sorted(est_df["category"].unique()):
                m = est_df["category"] == cat
                ax.scatter(est_df.loc[m, "product_id"], est_df.loc[m, "elasticity"],
                           label=cat, alpha=0.7, s=50)
            ax.set_xlabel("Product ID")
        else:
            ax.scatter(range(len(est_df)), est_df["elasticity"], alpha=0.7, s=50)
            ax.set_xlabel("Product index")
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax.set_ylabel("Estimated elasticity")
        ax.set_title("Estimated elasticity by product (GT not available)")
        ax.legend(fontsize=8)
        fig.tight_layout()
        save_fig(fig, "elasticity_scatter.png")

    save_json(metrics, "elasticity_metrics.json")
    logger.info("Elasticity evaluation complete.")


if __name__ == "__main__":
    run()
