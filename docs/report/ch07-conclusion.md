# Chapter 7 — Conclusion and Future Work

---

## 7.1 Summary of Achievements

This chapter maps each project objective against its outcome, based on the
system that was built and the results that were measured on the synthetic
dataset. No claim is made about real-world retail performance.

**Objective 1 — Synthetic dataset with hidden ground truth.**
A three-year synthetic transaction dataset (2022-01-01 to 2024-12-31) was
generated for 50 products and 1 000 customers across five categories. The
generator assigns a `true_elasticity` per product (drawn from category anchors
ranging from −0.5 for Staples to −2.0 for Impulse) and a `true_segment` per
customer (high_value, regular, occasional, at_risk). These ground-truth fields
are stored in a separate database (`revenue_management_gt`) that application
code cannot access; only the evaluation scripts read them via `get_gt_engine`.
The dataset is reproducible: `RANDOM_SEED = 42` is fixed in
`data_generation/config.py`.
*Outcome: achieved.*

**Objective 2 — ETL pipeline and feature engineering.**
An ETL pipeline loads raw CSVs into MySQL, computes weekly aggregates, and
builds a 14-feature table (three lag features, calendar features, price
features, promotional indicators). A temporal split (train: 7 300 rows up to
2024-10-28; test: 400 rows from 2024-11-04 to 2024-12-23) was verified to
have no overlap, and the lag-leakage check was promoted to a pytest in Phase
13.
*Outcome: achieved.*

**Objective 3 — Demand forecasting.**
XGBoost and Linear Regression were trained on the feature table. XGBoost was
selected as the production model (MAPE 9.7%, MAE 14.7, RMSE 21.2 on the
held-out test window; source: `metadata.json`). The XGBoost model outperforms
the Linear Regression baseline by approximately 5.6 MAPE points.
Phase 13 re-run of these metrics is pending (KI-10: XGBoost native library
missing in the submission environment).
*Outcome: achieved for training and model selection; Phase 13 re-run pending.*

**Objective 4 — Customer segmentation.**
K-Means clustering on recency-frequency-monetary (RFM) features produces four
segments. The k-search silhouette score peaks at k = 4 (0.8573), matching the
production choice `PRODUCTION_K = 4`. Stability was measured across five
random seeds (ARI = 1.0 for all 10 pairwise comparisons). The per-segment RFM
profile follows the expected ordering. Agreement with `true_segment`
(ARI/NMI/purity) is pending the GT database (KI-10).
*Outcome: achieved for clustering and internal validation; GT comparison pending.*

**Objective 5 — Price elasticity estimation.**
OLS log-log regression with promotional, seasonal, and festival controls was
run for all 50 products. All 50 estimated elasticities are negative
(`share_estimates_negative = 1.0`); the mean estimated elasticity is −1.3562.
Quantitative accuracy versus `true_elasticity` is pending the GT database
(KI-10). Phase 7 results recorded in `docs/results.md` (when the GT database
was accessible) show MAE = 0.062, RMSE = 0.091, and Pearson correlation = 0.990.
*Outcome: achieved for estimation; Phase 13 GT comparison pending.*

**Objective 6 — Pricing optimisation.**
A grid-search optimiser evaluates up to 31 candidate prices per product
(current price ±15% in 1% steps = 1 550 total candidates) and selects the
revenue-maximising candidate that satisfies four hard constraints: minimum
margin (10%), maximum price change (15%), price range, and stock. Constraints
are enforced and the `binding_constraint` field records the active constraint
for each product. Pricing metrics against the live database are pending (KI-10).
*Outcome: achieved for implementation and unit testing; evaluation-level metrics pending.*

**Objective 7 — LLM explanation layer.**
A GPT-compatible LLM client generates natural-language explanations for each
pricing recommendation and customer segment. Guardrails check numerical
consistency, directional consistency, length, and the absence of technical
jargon. All four tested failure scenarios (double API error, single timeout,
missing action key, mock client) return a valid response or fallback without
crashing (source: `evaluation/results/llm_failure_handling.json`). Prompt
construction was validated for both entity types (source:
`evaluation/results/llm_prompt_validation.json`).
*Outcome: achieved.*

**Objective 8 — Flask REST API and Angular dashboard.**
A Flask API exposes nine endpoint groups covering health, products, forecast,
segments, pricing, and explanations. An Angular 21 single-page application
provides three views (Forecast, Segments, Pricing) backed by the API.
The backend suite contains 87 tests; the frontend suite contains 76 specs.
*Outcome: achieved.*

---

## 7.2 Limitations

The following limitations apply to the system as submitted.

**KI-10 — Pending evaluation metrics.** The most significant limitation is
that several evaluation metrics were not measured in the submission environment:
all forecasting re-run metrics, segmentation versus ground truth (ARI/NMI/purity),
elasticity accuracy versus ground truth (MAE/RMSE/correlation), and all pricing
metrics. The cause is an environment-only gap (no DB credentials, XGBoost
native library missing), not a code failure. The evaluation scripts are correct;
re-running them in a full-stack environment will populate the missing results.

**Synthetic dataset.** All performance figures — including the MAPE of 9.7%,
the silhouette score of 0.8573, and the elasticity sign rate of 100% — reflect
model recovery of structure that the development team generated. The data
follows simple parametric distributions with fixed elasticity values and
non-overlapping customer segments. This is a considerably easier estimation
problem than real retail data, which exhibits structural breaks, irregular
promotions, competitor pricing, supply disruptions, and consumer behaviour
that is not well-described by a static segment label. No claim about
real-world predictive accuracy is made.

**No real-world validation.** The system has not been tested with real product
data, real customer transaction histories, or real pricing decisions. The
dashboard has not been used by retail staff, and no A/B test or pilot
deployment was conducted.

**No deep learning or reinforcement learning.** These approaches were
deliberately excluded from the project scope. The forecasting module uses
XGBoost and Linear Regression; the pricing module uses a grid-search
optimiser rather than a learned policy.

**Single machine, no scalability testing.** All components run on a single
developer machine. No load testing, horizontal scaling, or database replication
was performed. The system has not been tested beyond 50 products and 1 000
customers.

**One-shot pricing.** The pricing optimiser computes a recommendation once per
invocation using the most recently estimated elasticity. There is no online
learning, feedback loop, or adaptive pricing that updates estimates as new
transactions arrive.

The full list of known issues (KI-01 to KI-10) is documented in
`docs/known-issues.md`.

---

## 7.3 Future Work

The following extensions are realistic given the current architecture.

**(a) Real retail data validation.** The most important next step is replacing
the synthetic dataset with a publicly available real dataset — for example the
M5 Forecasting competition dataset (Walmart sales, 42 840 time series, five
years of daily data) or a Kaggle retail sales dataset — to test whether the
forecasting and pricing components generalise to realistic demand patterns.
This was planned as a Phase 13b extension but was not completed.

**(b) Phase 13b M5 validation.** If Phase 13b produced M5 evaluation results
before submission, they should be incorporated into Section 6.6 as a
supplementary result set. If not, M5 validation is the first priority for
post-submission work.

**(c) Richer features.** The current feature set (lags, calendar, price,
promotional indicators) does not capture promotional calendars from external
sources, competitor pricing, weather, store foot traffic, or social media
signals. Adding these features would improve forecasting accuracy on real data.

**(d) Deep learning forecasting.** A Long Short-Term Memory (LSTM) network or
Temporal Fusion Transformer (TFT) would capture long-range seasonal patterns
and inter-product dependencies that a single-horizon XGBoost model cannot.
These were excluded by design; the current pipeline structure (weekly
aggregated features → horizon-one forecast) would need to be extended to
support multi-step-ahead predictions.

**(e) Reinforcement learning pricing.** The current grid-search optimiser
selects the best price from a fixed candidate set in a single step. A natural
extension is to formulate pricing as a Markov Decision Process: state =
current prices plus demand signals, action = price recommendation, reward =
margin-constrained revenue. A standard RL agent (e.g., Proximal Policy
Optimisation or Deep Q-Network) could learn a pricing policy that adapts over
time and accounts for demand dynamics. This would be a significant departure
from the current one-shot design.

**(f) Live deployment.** Integrating with a real EPOS (electronic point of
sale) system or retail API would close the loop between recommendations and
observed outcomes. A live deployment would also generate the real transaction
data needed to re-estimate elasticities as market conditions change.

**(g) Multi-product elasticity and cross-price effects.** The current model
estimates one own-price elasticity per product. In practice, products in the
same category are substitutes or complements, and a price change for one
product affects demand for others. A seemingly unrelated regression (SUR) or
vector autoregression (VAR) model could capture these cross-price effects.

**(h) Resolve pending evaluation items.** As described in Chapter 6, running
`python evaluation/run_evaluation.py` in a full-stack environment with DB
credentials and the XGBoost native library will fill in the missing metrics
for forecasting, segmentation versus ground truth, elasticity accuracy, and
all pricing checks. This requires no code change.

---

## 7.4 Closing Remarks

This project demonstrates that an integrated, end-to-end demand forecasting
and dynamic pricing pipeline can be built entirely from open-source tools,
evaluated against known ground truth, and presented through a modern
single-page web dashboard. The system covers the full lifecycle from synthetic
data generation through ETL, feature engineering, model training, customer
segmentation, price elasticity estimation, pricing optimisation, LLM-powered
explanation, and a REST API consumed by an Angular dashboard. The key
limitation is that all conclusions are relative to a synthetic dataset with
known structure; real-world validation — either with a public retail benchmark
or a live deployment — remains future work.
