"""
Customer table generator.

Produces a DataFrame with one row per customer containing:

  Public columns (visible to ML models):
    customer_id : str — C0001 … C1000

  Ground-truth columns (must be withheld from model training):
    true_segment    : str   — high_value | regular | occasional | at_risk
    purchase_rate   : float — expected purchases per day (Poisson λ)
    basket_mean     : float — mean spend per transaction (£)
    basket_std      : float — std of spend per transaction (£)

  The purchase_rate / basket_mean / basket_std columns are derived from the
  segment and are needed by Phase 1b (sales generation) to simulate realistic
  buying behaviour.  They are ground-truth parameters — models in later phases
  must not see them.

Usage
-----
    from data_generation.customer import generate_customers
    df = generate_customers(rng)
"""

import numpy as np
import pandas as pd

from data_generation.config import NUM_CUSTOMERS, SEGMENTS


def generate_customers(rng: np.random.Generator) -> pd.DataFrame:
    """Return the Customer DataFrame.

    Parameters
    ----------
    rng : np.random.Generator
        Seeded generator passed in from the orchestrator.

    Returns
    -------
    pd.DataFrame
        Columns: customer_id, true_segment, purchase_rate,
                 basket_mean, basket_std.
    """
    segment_names = list(SEGMENTS.keys())
    weights = [SEGMENTS[s]["weight"] for s in segment_names]

    # Draw a segment label for every customer in a single vectorised call.
    # np.random.Generator has no direct weighted-choice shortcut for strings,
    # so we draw integer indices then map them.
    indices = rng.choice(len(segment_names), size=NUM_CUSTOMERS, p=weights)
    assigned_segments = [segment_names[i] for i in indices]

    rows = []
    for cust_num, seg_name in enumerate(assigned_segments, start=1):
        seg = SEGMENTS[seg_name]
        rows.append(
            {
                "customer_id": f"C{cust_num:04d}",
                # ── GROUND TRUTH — DO NOT USE AS MODEL FEATURES ─────────────
                "true_segment": seg_name,
                "purchase_rate": seg["purchase_rate"],
                "basket_mean": seg["basket_mean"],
                "basket_std": seg["basket_std"],
            }
        )

    df = pd.DataFrame(rows)
    df = df.astype(
        {
            "customer_id": "string",
            "true_segment": "string",
            "purchase_rate": "float64",
            "basket_mean": "float64",
            "basket_std": "float64",
        }
    )
    return df
