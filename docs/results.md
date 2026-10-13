# Results

Dataset: 50 products in 5 categories, 1000 customers, 2022-01-01 to 2024-12-31, about 1.3 million sales rows. Fixed seed.

## Demand forecasting (Phase 5)

Trained on 2022-01-17 to 2024-10-28, tested on the last 8 weeks (2024-11-04 to 2024-12-23). The last week of the data only has 2 days, so it is dropped.

| Model | MAE | RMSE | MAPE |
|---|---|---|---|
| Linear Regression | 17.65 | 24.26 | 15.26% |
| XGBoost | 14.73 | 21.19 | 9.72% |

XGBoost is used for the rest of the system.

## Price elasticity (Phase 7)

One regression per product on weekly data:
`log(units) = a + b*log(price/base_price) + promo_days + log(seasonal) + festival_days`

Compared with the true elasticity:

| | |
|---|---|
| MAE | 0.062 |
| RMSE | 0.091 |
| Correlation | 0.990 |
| Within 0.2 of true value | 96% |
| Correct sign | 100% |
| True value inside 95% CI | 94% |

| Category | Estimated | True | Generator setting |
|---|---|---|---|
| Staples | -0.519 | -0.510 | -0.5 |
| Personal Care | -1.013 | -0.964 | -1.0 |
| Electronics | -1.625 | -1.606 | -1.5 |
| Clothing | -1.743 | -1.728 | -1.8 |
| Impulse | -2.103 | -2.111 | -2.0 |

Running the regression on daily data gave MAE 0.088, so we use weekly data. Using the discounted price without a promo variable gave MAE 0.059, almost the same, because only about 5% of days have a promotion.

## Customer segmentation (Phase 6)

Clustering uses log frequency and log monetary value. Recency was dropped because every customer's last purchase was within 23 days.

| k | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|
| Silhouette | 0.733 | 0.808 | 0.857 | 0.778 | 0.670 |

k = 4 has the best Silhouette score. The elbow is at k = 3.

| Segment | Customers | Share of revenue |
|---|---|---|
| high_value | 160 | 40.1% |
| regular | 346 | 43.4% |
| occasional | 293 | 12.8% |
| at_risk | 201 | 3.8% |

Every customer is assigned to their true segment (ARI 1.0). With recency included, ARI drops to 0.63. The result is perfect because the generated segments don't overlap in purchase frequency (191-259 purchase days for at_risk, 401-492 for occasional, 805-908 for regular, 1020-1055 for high_value). Real data would not be this clean.

## Pricing (Phase 8)

Rules: margin at least 10% (unit cost is assumed), price change at most 15%, price within the range the product has sold at before.

- 1550 candidate prices, 1225 pass the rules. Rejections: 235 out of range, 122 below margin.
- 3 products already break the margin rule at their current price.

The numbers below were produced with the Linear Regression model in place of XGBoost and still need to be re-run with XGBoost:

| | |
|---|---|
| Price raised / cut / kept | 15 / 32 / 3 |
| Expected weekly revenue | +7.9% |
| Limited by | max change 32, price range 7, flat revenue 7, margin 4, stock 0 |
| Inelastic raised, elastic cut | 46 of 50 (the other 4 are explained by their limit) |
| Same direction using true elasticity | 48 of 50 |
| Revenue lost from elasticity error | 0.014% |

## LLM explanations (Phase 9)

54 explanations (50 products, 4 segments). Tested with the mock provider: all passed the checks, and a second run reused all of them from the cache. Not yet run with Gemini.
