import numpy as np
import pandas as pd

from data_generation.config import NUM_CUSTOMERS, SEGMENTS


def generate_customers(rng: np.random.Generator) -> pd.DataFrame:
    segment_names = list(SEGMENTS.keys())
    weights = [SEGMENTS[s]["weight"] for s in segment_names]

    indices = rng.choice(len(segment_names), size=NUM_CUSTOMERS, p=weights)
    assigned_segments = [segment_names[i] for i in indices]

    rows = []
    for cust_num, seg_name in enumerate(assigned_segments, start=1):
        seg = SEGMENTS[seg_name]
        rows.append(
            {
                "customer_id": f"C{cust_num:04d}",
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
