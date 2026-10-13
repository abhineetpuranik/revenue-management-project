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
    logger.info("Loading calendar data from MySQL...")
    with engine.connect() as conn:
        df_cal = pd.read_sql(_CALENDAR_SQL, conn, parse_dates=["date"])

    iso = df_cal["date"].dt.isocalendar()
    df_cal["iso_year"] = iso["year"].astype(int)
    df_cal["iso_week"] = iso["week"].astype(int)
    df_cal["week_start_date"] = df_cal["date"] - pd.to_timedelta(
        df_cal["date"].dt.dayofweek, unit="D"
    )

    weekly_cal = (
        df_cal
        .groupby(["iso_year", "iso_week", "week_start_date"], as_index=False)
        .agg(
            month                =("month",           "first"),
            seasonal_factor_mean =("seasonal_factor", "mean"),
            festival_week        =("festival_flag",   "max"),
        )
    )

    weekly_cal["month_sin"] = np.sin(2 * math.pi * (weekly_cal["month"] - 1) / 12)
    weekly_cal["month_cos"] = np.cos(2 * math.pi * (weekly_cal["month"] - 1) / 12)

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
