"""
Calendar table generator.

Produces a DataFrame with one row per calendar date in the configured range:

  date             : datetime.date — the calendar date
  year             : int
  month            : int  (1–12)
  weekday          : int  (0 = Monday … 6 = Sunday)
  weekday_name     : str  (Monday … Sunday)
  is_weekend       : bool
  seasonal_factor  : float — monthly demand multiplier (from config)
  weekday_factor   : float — day-of-week demand multiplier (from config)
  combined_factor  : float — seasonal_factor × weekday_factor (convenience
                             column; Phase 1b uses this directly)
  festival_flag    : int   — 1 if the date is in FESTIVAL_DATES, else 0

Usage
-----
    from data_generation.calendar import generate_calendar
    df = generate_calendar()
"""

import pandas as pd

from data_generation.config import (
    CALENDAR_END,
    CALENDAR_START,
    FESTIVAL_DATES,
    MONTHLY_SEASONAL_FACTORS,
    WEEKDAY_FACTORS,
)


def generate_calendar() -> pd.DataFrame:
    """Return the Calendar DataFrame.

    Calendar generation is fully deterministic given the config constants —
    no random draws are needed, so no rng argument is required.

    Returns
    -------
    pd.DataFrame
        One row per calendar date between CALENDAR_START and CALENDAR_END
        (inclusive).
    """
    dates = pd.date_range(start=CALENDAR_START, end=CALENDAR_END, freq="D")
    festival_set = set(pd.to_datetime(FESTIVAL_DATES).normalize())

    records = []
    for ts in dates:
        month = ts.month
        dow = ts.dayofweek          # 0 = Monday, 6 = Sunday
        s_factor = MONTHLY_SEASONAL_FACTORS[month]
        w_factor = WEEKDAY_FACTORS[dow]

        records.append(
            {
                "date": ts.date(),
                "year": ts.year,
                "month": month,
                "weekday": dow,
                "weekday_name": ts.day_name(),
                "is_weekend": dow >= 5,
                "seasonal_factor": s_factor,
                "weekday_factor": w_factor,
                "combined_factor": round(s_factor * w_factor, 4),
                "festival_flag": int(ts.normalize() in festival_set),
            }
        )

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])   # keep as datetime64 for easy joins
    df = df.astype(
        {
            "year": "int16",
            "month": "int8",
            "weekday": "int8",
            "weekday_name": "string",
            "is_weekend": "bool",
            "seasonal_factor": "float32",
            "weekday_factor": "float32",
            "combined_factor": "float32",
            "festival_flag": "int8",
        }
    )
    return df
