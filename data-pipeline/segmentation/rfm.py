from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)

_RFM_SQL = """
SELECT
    s.customer_id                     AS customer_id,
    MAX(s.date)                       AS last_purchase_date,
    COUNT(DISTINCT s.date)            AS frequency,
    SUM(CAST(s.revenue AS DOUBLE))    AS monetary,
    COUNT(*)                          AS sales_rows
FROM sales s
GROUP BY s.customer_id
"""
_CUSTOMERS_SQL = "SELECT customer_id FROM customer ORDER BY customer_id"
_CAL_SQL = "SELECT MIN(date) AS first_date, MAX(date) AS last_date FROM calendar"


def compute_rfm(engine) -> tuple[pd.DataFrame, pd.Timestamp]:
    with engine.connect() as conn:
        agg = pd.read_sql(text(_RFM_SQL), conn)
        customers = pd.read_sql(text(_CUSTOMERS_SQL), conn)
        cal = pd.read_sql(text(_CAL_SQL), conn)

    first_date = pd.to_datetime(cal["first_date"].iloc[0])
    snapshot = pd.to_datetime(cal["last_date"].iloc[0]) + pd.Timedelta(days=1)

    rfm = customers.merge(agg, on="customer_id", how="left")
    rfm["has_purchases"] = rfm["frequency"].notna()
    rfm["last_purchase_date"] = pd.to_datetime(rfm["last_purchase_date"])
    rfm["frequency"] = rfm["frequency"].fillna(0).astype(int)
    rfm["monetary"] = rfm["monetary"].fillna(0.0).astype(float)
    rfm["sales_rows"] = rfm["sales_rows"].fillna(0).astype(int)

    never_days = (snapshot - first_date).days + 1
    rfm["recency_days"] = (snapshot - rfm["last_purchase_date"]).dt.days
    rfm["recency_days"] = rfm["recency_days"].fillna(never_days).astype(int)

    logger.info("RFM computed for %d customers (%d without purchases); snapshot %s.",
                len(rfm), int((~rfm["has_purchases"]).sum()), snapshot.date())
    return rfm[["customer_id", "recency_days", "frequency", "monetary", "sales_rows",
                "last_purchase_date", "has_purchases"]], snapshot
