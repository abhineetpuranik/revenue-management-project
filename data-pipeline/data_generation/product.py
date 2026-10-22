import numpy as np
import pandas as pd

from data_generation.config import CATEGORIES, PRICE_DECIMALS

def generate_products(rng: np.random.Generator) -> pd.DataFrame:
    rows: list[dict] = []
    product_counter = 1

    for category, cfg in CATEGORIES.items():
        for _ in range(cfg["product_count"]):
            pid = f"P{product_counter:03d}"

            base_price = round(
                float(rng.uniform(cfg["price_min"], cfg["price_max"])), PRICE_DECIMALS
            )

            base_demand = int(rng.poisson(cfg["demand_mean"]))
            base_demand = max(1, base_demand)

            elasticity = float(
                rng.normal(
                    loc=cfg["elasticity_anchor"],
                    scale=cfg["elasticity_noise_std"],
                )
            )
            elasticity = min(elasticity, -0.10)

            rows.append(
                {
                    "product_id": pid,
                    "category": category,
                    "base_price": base_price,
                    "base_demand": base_demand,
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
