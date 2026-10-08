"""
Calendar features — Phase 4 feature engineering.

Builds weekly-granularity calendar features from the MySQL calendar table.

Features produced
-----------------
  month                : int   1–12 (of the week's Monday)
  month_sin            : float cyclical sine encoding of month
  month_cos            : float cyclical cosine encoding of month
  seasonal_factor_mean : float mean of daily seasonal_factor over the week
  festival_week        : int   1 if any day in the week has festival_flag=1

Encoding choice: cyclical (sin/cos) for month
---------------------------------------------
Month is an ordinal variable on a circle (December wraps back to January).
Linear encoding (1–12) gives December a distance of 11 from January even
though they are actually adjacent.  Cyclical sin/cos encoding preserves
the circular topology:

    month_sin = sin(2π × (month - 1) / 12)
    month_cos = cos(2π × (month - 1) / 12)

This means the feature space is continuous across the December-January
boundary.  Both columns together uniquely identify the month, so no
information is lost.

seasonal_factor_mean is kept as a numeric feature because it already
encodes the month-level demand multiplier directly; having both it and
the cyclical month encoding gives the model two complementary signals.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_CALENDAR_SQL = """
SELECT
    date,
    month,
    seasonal_factor,
    festival_flag
FROM revenue_management.calendar
ORDER BY date
"""


def load_calendar_features(engine: Engine) -> pd.DataFrame:
    """
    Return a DataFrame of calendar features at weekly granularity.

    Parameters
    ----------
    engine : SQLAlchemy Engine connected to revenue_management.

    Returns
    -------
    pd.DataFrame with columns:
        iso_year, iso_week, week_start_date,
        month, month_sin, month_cos,
        seasonal_factor_mean, festival_week
    """
    logger.info("Loading calendar data from MySQL...")
    with engine.connect() as conn:
        df_cal = pd.read_sql(_CALENDAR_SQL, conn, parse_dates=["date"])

    # ── ISO week derivation ───────────────────────────────────────────────
    iso = df_cal["date"].dt.isocalendar()
    df_cal["iso_year"] = iso["year"].astype(int)
    df_cal["iso_week"] = iso["week"].astype(int)
    df_cal["week_start_date"] = df_cal["date"] - pd.to_timedelta(
        df_cal["date"].dt.dayofweek, unit="D"
    )

    # ── Aggregate to weekly ───────────────────────────────────────────────
    weekly_cal = (
        df_cal
        .groupby(["iso_year", "iso_week", "week_start_date"], as_index=False)
        .agg(
            month                =("month",           "first"),   # Monday's month
            seasonal_factor_mean =("seasonal_factor", "mean"),
            festival_week        =("festival_flag",   "max"),     # 1 if any day is festival
        )
    )

    # ── Cyclical month encoding ───────────────────────────────────────────
    weekly_cal["month_sin"] = np.sin(2 * math.pi * (weekly_cal["month"] - 1) / 12)
    weekly_cal["month_cos"] = np.cos(2 * math.pi * (weekly_cal["month"] - 1) / 12)

    # ── Type casts ────────────────────────────────────────────────────────
    weekly_cal["festival_week"] = weekly_cal["festival_week"].astype(int)
    weekly_cal["month"]         = weekly_cal["month"].astype(int)

    weekly_cal = weekly_cal.sort_values(["iso_year", "iso_week"]).reset_index(drop=True)

    logger.info("Calendar features built: %d week rows.", len(weekly_cal))
    return weekly_cal[
        [
            "iso_year", "iso_week", "week_start_date",
            "month", "month_sin", "month_cos",
            "seasonal_factor_mean", "festival_week",
        ]
    ]
