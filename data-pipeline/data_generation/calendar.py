import pandas as pd

from data_generation.config import (
    CALENDAR_END,
    CALENDAR_START,
    FESTIVAL_DATES,
    MONTHLY_SEASONAL_FACTORS,
    WEEKDAY_FACTORS,
)


def generate_calendar() -> pd.DataFrame:
    dates = pd.date_range(start=CALENDAR_START, end=CALENDAR_END, freq="D")
    festival_set = set(pd.to_datetime(FESTIVAL_DATES).normalize())

    records = []
    for ts in dates:
        month = ts.month
        dow = ts.dayofweek
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
    df["date"] = pd.to_datetime(df["date"])
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
