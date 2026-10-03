"""
Product table generator.

Produces a DataFrame with one row per product containing:

  Public columns (visible to ML models):
    product_id   : str  — P001 … P050
    category     : str  — one of the five CATEGORIES keys
    base_price   : float — realistic price for the category (2 d.p.)
    base_demand  : int   — average units sold per day under normal conditions

  Ground-truth columns (must be withheld from model training):
    true_elasticity : float — price elasticity of demand; negative by
                              construction.  Staples ≈ -0.5, Impulse ≈ -2.0.

Usage
-----
    from data_generation.product import generate_products
    df = generate_products(rng)
"""

import numpy as np
import pandas as pd

from data_generation.config import CATEGORIES


def generate_products(rng: np.random.Generator) -> pd.DataFrame:
    """Return the Product DataFrame.

    Parameters
    ----------
    rng : np.random.Generator
        Seeded generator passed in from the orchestrator so the entire run
        shares a single seed chain.

    Returns
    -------
    pd.DataFrame
        Columns: product_id, category, base_price, base_demand,
                 true_elasticity.
    """
    rows: list[dict] = []
    product_counter = 1

    for category, cfg in CATEGORIES.items():
        for _ in range(cfg["product_count"]):
            pid = f"P{product_counter:03d}"

            # base_price: uniform draw within the category price band, rounded
            # to 2 decimal places (retail convention: .99 endings handled
            # naturally by rounding rather than forcing them — keeps the
            # distribution realistic without introducing artificial spikes).
            base_price = round(
                float(rng.uniform(cfg["price_min"], cfg["price_max"])), 2
            )

            # base_demand: Poisson draw so values are non-negative integers
            # with realistic day-to-day variance around the category mean.
            base_demand = int(rng.poisson(cfg["demand_mean"]))
            # Floor at 1 so no product has zero expected demand.
            base_demand = max(1, base_demand)

            # true_elasticity: Gaussian noise around the category anchor.
            # Clamped so staples can never exceed -0.10 (near-perfectly
            # inelastic) and premium/impulse can never be positive.
            elasticity = float(
                rng.normal(
                    loc=cfg["elasticity_anchor"],
                    scale=cfg["elasticity_noise_std"],
                )
            )
            # Enforce elasticity < 0 (demand always falls when price rises)
            # and a sensible ceiling of -0.10 so the value is always negative.
            elasticity = min(elasticity, -0.10)

            rows.append(
                {
                    "product_id": pid,
                    "category": category,
                    "base_price": base_price,
                    "base_demand": base_demand,
                    # ── GROUND TRUTH — DO NOT USE AS MODEL FEATURE ──────────
                    "true_elasticity": round(elasticity, 4),
                }
            )
            product_counter += 1

    df = pd.DataFrame(rows)
    df = df.astype(
        {
            "product_id": "string",
            "category": "string",
            "base_price": "float64",
            "base_demand": "int64",
            "true_elasticity": "float64",
        }
    )
    return df
