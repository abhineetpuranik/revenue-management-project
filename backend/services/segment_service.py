"""
Segmentation service — no Flask-specific code.

Provides:
  get_segment_summary(engine)
      → dict for GET /api/segments

  get_customers_page(engine, segment, page, page_size)
      → dict for GET /api/segments/customers

  get_customer_segment(engine, customer_id)
      → dict for GET /api/customers/<customer_id>/segment

Note on Silhouette score
------------------------
The silhouette score (0.8573) and number of clusters (4) produced by Phase 6
are not stored in MySQL — the segment_summary table has only RFM statistics.
These two values are embedded as constants here.  When Phase 6 is re-run the
service must be updated if they change.  This is a known limitation; storing
them in MySQL would require adding a column to segment_summary in a future
phase.
"""

from __future__ import annotations

from sqlalchemy import text

_SILHOUETTE_SCORE: float = 0.8573
_N_CLUSTERS:       int   = 4

_SUMMARY_SQL = text("""
    SELECT
        segment_label,
        customer_count,
        share_pct,
        mean_recency_days,
        median_recency_days,
        mean_frequency,
        median_frequency,
        mean_monetary,
        median_monetary,
        revenue_share_pct
    FROM segment_summary
    ORDER BY
        CASE segment_label
            WHEN 'high_value'  THEN 1
            WHEN 'regular'     THEN 2
            WHEN 'occasional'  THEN 3
            WHEN 'at_risk'     THEN 4
            ELSE 5
        END
""")

_CUSTOMER_COUNT_SQL = text("""
    SELECT COUNT(*) AS n
    FROM customer_rfm_segment
    WHERE (:segment IS NULL OR segment_label = :segment)
""")

_CUSTOMERS_PAGE_SQL = text("""
    SELECT customer_id, segment_label, recency_days, frequency, monetary
    FROM customer_rfm_segment
    WHERE (:segment IS NULL OR segment_label = :segment)
    ORDER BY customer_id
    LIMIT :limit OFFSET :offset
""")

_CUSTOMER_SQL = text("""
    SELECT customer_id, segment_label, recency_days, frequency, monetary
    FROM customer_rfm_segment
    WHERE customer_id = :cid
""")

_SEGMENT_EXISTS_SQL = text("""
    SELECT COUNT(*) AS n FROM segment_summary WHERE segment_label = :label
""")


def get_segment_summary(engine) -> dict:
    """Return the segment summary with metadata."""
    with engine.connect() as conn:
        rows = conn.execute(_SUMMARY_SQL).fetchall()

    segments = [
        {
            "segment_label":      r.segment_label,
            "customer_count":     int(r.customer_count),
            "share_pct":          float(r.share_pct),
            "revenue_share_pct":  float(r.revenue_share_pct),
            "mean_recency_days":  float(r.mean_recency_days),
            "median_recency_days": float(r.median_recency_days),
            "mean_frequency":     float(r.mean_frequency),
            "median_frequency":   float(r.median_frequency),
            "mean_monetary":      float(r.mean_monetary),
            "median_monetary":    float(r.median_monetary),
        }
        for r in rows
    ]

    total_customers = sum(s["customer_count"] for s in segments)

    return {
        "n_clusters":       _N_CLUSTERS,
        "silhouette_score": _SILHOUETTE_SCORE,
        "total_customers":  total_customers,
        "segments":         segments,
    }


def segment_label_exists(engine, label: str) -> bool:
    with engine.connect() as conn:
        n = conn.execute(_SEGMENT_EXISTS_SQL, {"label": label}).scalar()
    return int(n) > 0


def get_customers_page(
    engine,
    segment: str | None,
    page: int,
    page_size: int,
) -> dict:
    """
    Return a paginated list of customers with their segment and RFM values.

    Parameters
    ----------
    engine    : SQLAlchemy engine
    segment   : optional segment_label filter
    page      : 1-based page number
    page_size : rows per page

    Returns
    -------
    dict with keys: total, page, page_size, pages, customers (list)
    """
    params_count = {"segment": segment}
    with engine.connect() as conn:
        total = int(conn.execute(_CUSTOMER_COUNT_SQL, params_count).scalar())
        offset = (page - 1) * page_size
        params_page = {"segment": segment, "limit": page_size, "offset": offset}
        rows = conn.execute(_CUSTOMERS_PAGE_SQL, params_page).fetchall()

    customers = [
        {
            "customer_id":   r.customer_id,
            "segment_label": r.segment_label,
            "recency_days":  int(r.recency_days),
            "frequency":     int(r.frequency),
            "monetary":      float(r.monetary),
        }
        for r in rows
    ]

    import math
    return {
        "total":     total,
        "page":      page,
        "page_size": page_size,
        "pages":     math.ceil(total / page_size) if page_size else 1,
        "customers": customers,
    }


def get_customer_segment(engine, customer_id: str) -> dict | None:
    """Return one customer's segment and RFM, or None if not found."""
    with engine.connect() as conn:
        row = conn.execute(_CUSTOMER_SQL, {"cid": customer_id}).fetchone()

    if row is None:
        return None

    return {
        "customer_id":   row.customer_id,
        "segment_label": row.segment_label,
        "recency_days":  int(row.recency_days),
        "frequency":     int(row.frequency),
        "monetary":      float(row.monetary),
    }
