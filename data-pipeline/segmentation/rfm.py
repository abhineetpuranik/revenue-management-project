"""
RFM features — Phase 6 (Module 3).

Computes Recency, Frequency and Monetary value per customer from the sales
table (application schema only).

Definitions
-----------
snapshot_date : the day AFTER the last date in the calendar table
recency_days  : snapshot_date − customer's last purchase date (days; lower = more recent)
frequency     : number of DISTINCT purchase dates. One shopping visit can create
                several sales rows (one per product), so counting rows would
                measure basket breadth, not how often the customer shops.
monetary      : total revenue across all the customer's sales rows

Customers in the customer table with no sales rows are NOT dropped: they get
frequency = 0, monetary = 0, recency_days = days since the first calendar day
+ 1 (i.e. "never purchased in the window"), and are reported by the orchestrator.

Ground-truth isolation: this module never reads the ground-truth schema.
"""

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
    """
    Returns (rfm, snapshot_date). rfm has one row per customer in the customer
    table: customer_id, recency_days, frequency, monetary, sales_rows,
    last_purchase_date, has_purchases.
    """
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
