from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

_FEATURES_SQL = """
SELECT product_id, iso_year, iso_week, week_start_date, units_sold, list_price_mean
FROM forecast_features
ORDER BY product_id, week_start_date
"""
_CALENDAR_SQL = "SELECT date, month, seasonal_factor, festival_flag FROM calendar ORDER BY date"


def _calendar_for_week(cal: pd.DataFrame, week_start: pd.Timestamp) -> pd.DataFrame:
    cal_idx = cal.set_index("date")
    rows = []
    for i in range(7):
        d = week_start + pd.Timedelta(days=i)
        src = d
        if d not in cal_idx.index:
            try:
                src = d.replace(year=d.year - 1)
            except ValueError:
                src = (d - pd.Timedelta(days=1)).replace(year=d.year - 1)
        r = cal_idx.loc[src]
        rows.append({"date": d, "source_date": src, "seasonal_factor": float(r["seasonal_factor"]),
                     "festival_flag": int(r["festival_flag"])})
    return pd.DataFrame(rows)


def build_base_rows(engine) -> tuple[pd.DataFrame, dict]:
    with engine.connect() as conn:
        ff = pd.read_sql(text(_FEATURES_SQL), conn)
        cal = pd.read_sql(text(_CALENDAR_SQL), conn)
    ff["week_start_date"] = pd.to_datetime(ff["week_start_date"])
    cal["date"] = pd.to_datetime(cal["date"])
    last_day = cal["date"].max()

    complete = ff[ff["week_start_date"] + pd.Timedelta(days=6) <= last_day]
    last_week_start = complete["week_start_date"].max()
    forecast_start = last_week_start + pd.Timedelta(days=7)
    iso = forecast_start.isocalendar()

    days = _calendar_for_week(cal, forecast_start)
    month = int(forecast_start.month)
    cal_feats = {
        "month": month,
        "month_sin": math.sin(2 * math.pi * (month - 1) / 12),
        "month_cos": math.cos(2 * math.pi * (month - 1) / 12),
        "seasonal_factor_mean": float(days["seasonal_factor"].mean()),
        "festival_week": int(days["festival_flag"].max()),
    }

    rows = []
    for pid, g in complete.groupby("product_id", sort=True):
        g = g.sort_values("week_start_date")
        last3 = g.tail(3)["units_sold"].to_numpy()[::-1]
        if len(last3) < 3 or g["week_start_date"].iloc[-1] != last_week_start:
            raise RuntimeError(f"{pid}: fewer than 3 complete weeks ending {last_week_start.date()}")
        rows.append({"product_id": pid,
                     "lag_1_units": float(last3[0]), "lag_2_units": float(last3[1]),
                     "lag_3_units": float(last3[2]),
                     "prev_list_price_mean": float(g["list_price_mean"].iloc[-1]),
                     **cal_feats})
    info = {
        "forecast_week": f"{iso[0]}-W{iso[1]:02d}",
        "forecast_week_start": forecast_start.date(),
        "last_complete_week_start": last_week_start.date(),
        "calendar_days_borrowed_from_previous_year":
            int((days["date"] != days["source_date"]).sum()),
        **cal_feats,
    }
    logger.info("Forecast week %s (starts %s); lags from weeks ending %s.",
                info["forecast_week"], forecast_start.date(), last_week_start.date())
    return pd.DataFrame(rows), info


def rows_at_prices(base: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.merge(base, on="product_id", how="left")
    p = df["price"].astype(float)
    df["list_price_mean"] = p
    df["price_change_pct"] = p / df["prev_list_price_mean"] - 1.0
    df["avg_price"] = p
    df["avg_discount"] = 0.0
    df["avg_discount_price"] = 0.0
    df["promo_days"] = 0
    return df
