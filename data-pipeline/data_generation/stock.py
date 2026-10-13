from __future__ import annotations

import numpy as np
import pandas as pd

from data_generation.config import (
    INITIAL_STOCK_MULTIPLIER,
    RESTOCK_INTERVAL_DAYS,
    RESTOCK_PERIOD_MULTIPLIER,
)

__all__ = ["generate_stock"]


def generate_stock(
    df_products: pd.DataFrame,
    df_calendar: pd.DataFrame,
    df_daily_units: pd.DataFrame,
) -> pd.DataFrame:
    dates = pd.to_datetime(df_calendar["date"].values)
    n_dates = len(dates)

    date_index: dict[pd.Timestamp, int] = {d: i for i, d in enumerate(dates)}

    products_list = df_products["product_id"].tolist()
    prod_index: dict[str, int] = {p: i for i, p in enumerate(products_list)}
    n_products = len(products_list)

    sold_matrix = np.zeros((n_products, n_dates), dtype=np.int64)
    for _, row in df_daily_units.iterrows():
        pi = prod_index.get(row["product_id"])
        di = date_index.get(pd.Timestamp(row["date"]))
        if pi is not None and di is not None:
            sold_matrix[pi, di] = int(row["units_sold"])

    all_rows: list[pd.DataFrame] = []

    for prod_i, (_, prod) in enumerate(df_products.iterrows()):
        pid: str = prod["product_id"]
        base_demand: int = int(prod["base_demand"])

        initial_stock = base_demand * INITIAL_STOCK_MULTIPLIER
        weekly_restock_qty = int(
            round(base_demand * 7 * RESTOCK_PERIOD_MULTIPLIER)
        )

        stock_levels     = np.empty(n_dates, dtype=np.int64)
        units_restocked  = np.zeros(n_dates, dtype=np.int64)
        stockout_flags   = np.zeros(n_dates, dtype=np.int8)

        current_stock = initial_stock

        for day_i in range(n_dates):
            restock = 0
            if day_i % RESTOCK_INTERVAL_DAYS == 0:
                restock = weekly_restock_qty
                current_stock += restock
            units_restocked[day_i] = restock

            sold_today = int(sold_matrix[prod_i, day_i])

            if sold_today > current_stock:
                stockout_flags[day_i] = 1
                current_stock = 0
            else:
                current_stock -= sold_today

            stock_levels[day_i] = current_stock

        df_prod = pd.DataFrame(
            {
                "product_id":      pid,
                "date":            dates,
                "stock_level":     stock_levels,
                "units_restocked": units_restocked,
                "stockout_flag":   stockout_flags,
            }
        )
        all_rows.append(df_prod)

    df_stock = pd.concat(all_rows, ignore_index=True)
    df_stock = df_stock.astype(
        {
            "product_id":      "string",
            "stock_level":     "int64",
            "units_restocked": "int64",
            "stockout_flag":   "int8",
        }
    )
    return df_stock
