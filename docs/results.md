# Results so far (Phases 5–9)

All figures come from the synthetic dataset: 50 products in 5 categories, 1,000 customers, 2022-01-01 to 2024-12-31, about 1.3 M sales rows, fixed seed. Runs are deterministic. Hidden ground truth (`true_elasticity`, `true_segment`) is used only for validation.

---

## Phase 5 — Demand forecasting

Time-based split: train 2022-01-17 → 2024-10-28 (7,300 product-weeks), test the last 8 weeks, 2024-11-04 → 2024-12-23 (400 product-weeks). The partial final week (2 days) is dropped.

| Model | MAE | RMSE | MAPE |
|---|---|---|---|
| Linear Regression (baseline) | 17.65 | 24.26 | 15.26 % |
| **XGBoost (selected)** | **14.73** | **21.19** | **9.72 %** |

XGBoost wins on RMSE by 12.7 %.

---

## Phase 7 — Price elasticity

Per-product OLS at weekly grain: `log(units) = a + β·log(price/base_price) + promo_days + log(seasonal) + festival_days`.

| Metric vs. true elasticity | Value |
|---|---|
| MAE / RMSE | 0.062 / 0.091 |
| Correlation | 0.990 |
| Within ±0.2 | 96 % |
| Correct sign | 100 % |
| 95 % CI coverage | 94 % |

| Category | Mean estimate | Mean true | Generator anchor |
|---|---|---|---|
| Staples | −0.519 | −0.510 | −0.5 |
| Personal Care | −1.013 | −0.964 | −1.0 |
| Electronics | −1.625 | −1.606 | −1.5 |
| Clothing | −1.743 | −1.728 | −1.8 |
| Impulse | −2.103 | −2.111 | −2.0 |

Design comparison: the daily specification (dropping zero-sales days) gives MAE 0.088, so it is worse. A price_at_sale specification without a promo control gives MAE 0.059, about the same, because promotions are only about 5 % of days. List price was kept because it matches how demand is generated.

---

## Phase 6 — Customer segmentation

RFM → log + standardise → K-Means. Recency was excluded from clustering: every customer bought within the last 23 days, below the 30-day informativeness threshold.

| k | 2 | 3 | **4** | 5 | 6 |
|---|---|---|---|---|---|
| Silhouette | 0.733 | 0.808 | **0.857** | 0.778 | 0.670 |

Best Silhouette at k = 4; the elbow (max second difference) is at k = 3.

| Segment | Customers | Revenue share |
|---|---|---|
| high_value | 160 | 40.1 % |
| regular | 346 | 43.4 % |
| occasional | 293 | 12.8 % |
| at_risk | 201 | 3.8 % |

Against `true_segment`: **100 % accuracy, ARI 1.0, NMI 1.0**. With recency included, ARI drops to 0.63. The perfect score reflects that the generated segments have non-overlapping purchase frequencies (at_risk 191–259 purchase days, occasional 401–492, regular 805–908, high_value 1,020–1,055). Real data would not separate this cleanly.

---

## Phase 8 — Pricing

Rules: margin ≥ 10 % (on an **assumed** cost = base price × category ratio), change ≤ ±15 %, price within its historical range, no change if the elasticity estimate is unreliable.

- 8a: 1,550 candidate prices, 1,225 pass (rejections: PRICE_RANGE 235, MARGIN 122). Three products already break the margin rule at their current price.
- 8b: forecast week 2025-W01. Demand = Phase 5 forecast at the current price × (p / p_current)^β, capped by stock + weekly restock.

> ⚠️ The 8b figures below were produced with Phase 5's **Linear Regression** model standing in for XGBoost (the development sandbox had no XGBoost). Re-run `python -m pricing.run_pricing` with the real model and update this section before quoting the numbers.

| | |
|---|---|
| Raised / cut / held | 15 / 32 / 3 |
| Expected weekly revenue | +7.9 % |
| Binding rule | MAX_CHANGE 32 · PRICE_RANGE 7 · TIE_TOLERANCE 7 · MARGIN 4 · STOCK 0 |
| Follows "inelastic → raise, elastic → cut" | 46 / 50 (all 4 exceptions explained by their binding rule) |
| Same decision with the TRUE elasticity | direction 48 / 50, identical price 45 / 50 |
| Revenue lost from estimation error | 0.014 % |

---

## Phase 9 — LLM explanations

54 explanations (50 pricing + 4 segments). Mock run: all pass guardrails first time; a second run reused all 54 from cache (0 LLM calls).

> ⚠️ Not yet run against live Gemini. After running with `LLM_PROVIDER=gemini`, record here how many passed first time, passed on retry, or fell back to the template.
