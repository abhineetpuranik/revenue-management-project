# Open Items

Every placeholder, [CITATION NEEDED], [TEAM TO FILL], and [TEAM TO CONFIRM] item grouped by location. The team must resolve all items before submission.

---

## front-matter.md

### TEAM TO FILL — Personal and institutional information

- [TEAM TO FILL] Project title | file: front-matter.md | context: Title Page
- [TEAM TO FILL] Degree title (e.g. Bachelor of Engineering / B.Tech in Computer Science and Engineering) | file: front-matter.md | context: Title Page
- [TEAM TO FILL] Student 1 full name and roll number | file: front-matter.md | context: Title Page and Declaration
- [TEAM TO FILL] Student 2 full name and roll number | file: front-matter.md | context: Title Page and Declaration
- [TEAM TO FILL] Student 3 full name and roll number | file: front-matter.md | context: Title Page and Declaration
- [TEAM TO FILL] Supervisor name and designation | file: front-matter.md | context: Title Page and Certificate
- [TEAM TO FILL] Department name | file: front-matter.md | context: Title Page
- [TEAM TO FILL] Institution name | file: front-matter.md | context: Title Page, Certificate, and Declaration
- [TEAM TO FILL] Submission month and year | file: front-matter.md | context: Title Page
- [TEAM TO FILL] Certificate date | file: front-matter.md | context: Certificate
- [TEAM TO FILL] Declaration dates (one per student) | file: front-matter.md | context: Declaration
- [TEAM TO FILL] Acknowledgements section | file: front-matter.md | context: Acknowledgements

---

## ch01-introduction.md

### TEAM TO CONFIRM — Problem statement and objectives

- [TEAM TO CONFIRM] Problem statement — confirm this matches the approved synopsis | file: ch01-introduction.md | context: §1.2 Problem Statement
- [TEAM TO CONFIRM] Objectives list — add, remove, or reword objectives to match the approved synopsis | file: ch01-introduction.md | context: §1.3 Objectives
- [TEAM TO CONFIRM] AI coding tools used — state which tools (e.g. Kiro, GitHub Copilot) were used, in which phases, and to what extent | file: ch01-introduction.md | context: §1.6 Summary of Contributions

---

## ch02-literature-review.md

### CITATION NEEDED — Academic references

- [CITATION NEEDED] Hyndman & Athanasopoulos — confirm edition (likely 3rd ed.), year (likely 2021), publisher, and URL (https://otexts.com/fpp3/) | file: ch02-literature-review.md | context: §2.1 Demand Forecasting — ARIMA and exponential smoothing
- [CITATION NEEDED] Chen & Guestrin — XGBoost paper: confirm year, KDD proceedings page numbers and DOI | file: ch02-literature-review.md | context: §2.1 Demand Forecasting — XGBoost
- [CITATION NEEDED] Makridakis, Spiliotis & Assimakopoulos — M5 competition paper: confirm journal, year, volume, issue, page numbers, DOI | file: ch02-literature-review.md | context: §2.1 Demand Forecasting — M5 benchmark
- [CITATION NEEDED] Lim, Arık, Loeff & Pfister — Temporal Fusion Transformers paper: confirm journal, year, volume, issue, page numbers, DOI | file: ch02-literature-review.md | context: §2.1 Demand Forecasting — deep learning methods
- [CITATION NEEDED] Hughes — RFM framework: confirm whether to cite *Strategic Database Marketing* (1994) or the 1996 journal article; confirm publisher, location, and page numbers | file: ch02-literature-review.md | context: §2.2 Customer Segmentation — RFM
- [CITATION NEEDED] Kaufman & Rousseeuw — K-Means / cluster analysis textbook (1990, Wiley): confirm publisher location and ISBN; or confirm preference for Lloyd (1982) IEEE paper instead | file: ch02-literature-review.md | context: §2.2 Customer Segmentation — K-Means
- [CITATION NEEDED] Rousseeuw — Silhouette paper (1987): confirm journal, volume, issue, page numbers, DOI | file: ch02-literature-review.md | context: §2.2 Customer Segmentation — silhouette coefficient
- [CITATION NEEDED] Econometrics textbook for price elasticity / log-log OLS — confirm whether to cite Varian *Intermediate Microeconomics* (9th ed., W. W. Norton, 2014) or Wooldridge *Introductory Econometrics* (7th ed., Cengage, 2019); confirm edition, year, and publisher details | file: ch02-literature-review.md | context: §2.3 Price Elasticity
- [CITATION NEEDED] Talluri & van Ryzin — *The Theory and Practice of Revenue Management* (Springer, 2004): confirm publisher location, ISBN, and DOI | file: ch02-literature-review.md | context: §2.4 Dynamic Pricing — revenue management foundations
- [CITATION NEEDED] Sutton & Barto — *Reinforcement Learning: An Introduction* (2nd ed., MIT Press, 2018): confirm publisher location, ISBN, and URL | file: ch02-literature-review.md | context: §2.4 Dynamic Pricing — RL framing
- [CITATION NEEDED] Representative RL-for-pricing paper — confirm author(s), title, journal or venue, year, volume, page numbers, DOI (e.g. den Boer 2015 survey, or a more recent deep RL pricing paper) | file: ch02-literature-review.md | context: §2.4 Dynamic Pricing — RL applied to pricing

---

## ch06-testing-evaluation.md

### PENDING evaluation items

- [PENDING] Data-pipeline test suite: run `cd data-pipeline && pytest tests/ -v` with full environment to count `@NEEDS_DB` skips vs passes. Command will produce output showing exact pass/skip breakdown. Result file: terminal output | file: ch06-testing-evaluation.md | context: §6.1 Test Summary table
- [PENDING] Backend test suite: run `cd backend && pytest tests/ -v` with DB credentials to count `@NEEDS_DB` skips vs passes. Result file: terminal output | file: ch06-testing-evaluation.md | context: §6.1 Test Summary table
- [PENDING] XGBoost re-evaluation (MAE, RMSE, MAPE on held-out window): run `python evaluation/run_evaluation.py --only forecasting` with working XGBoost install (`brew install libomp` on macOS) and populated `data-pipeline/.env`. Result file: `evaluation/results/forecasting_metrics.json` | file: ch06-testing-evaluation.md | context: §6.3 Demand Forecasting Evaluation
- [PENDING] Per-category MAPE breakdown: same run as above. Result file: `evaluation/results/forecasting_by_category.csv` | file: ch06-testing-evaluation.md | context: §6.3 Demand Forecasting Evaluation
- [PENDING] Per-product MAPE distribution (median, 90th pct, worst 10): same run. Result file: `evaluation/results/forecasting_per_product.csv` | file: ch06-testing-evaluation.md | context: §6.3 Demand Forecasting Evaluation
- [PENDING] Forecasting leakage check: same run. Result file: `evaluation/results/forecasting_leakage_check.json` | file: ch06-testing-evaluation.md | context: §6.3 Demand Forecasting Evaluation
- [PENDING] Five forecasting figure PNGs: same run. Result files: `evaluation/results/forecasting_*.png` | file: ch06-testing-evaluation.md | context: §6.3 figures
- [PENDING] System training times and API response times: same run. Result files: `evaluation/results/system_training_times.json`, `evaluation/results/system_api_response_times.json` | file: ch06-testing-evaluation.md | context: §6.7 System Performance
- [PENDING] Segmentation ARI/NMI/purity vs `true_segment`: run `python evaluation/run_evaluation.py --only segmentation` with the GT DB reachable (`data-pipeline/.env` containing `DB_GT_NAME=revenue_management_gt`). Result file: `evaluation/results/segmentation_vs_ground_truth.json` | file: ch06-testing-evaluation.md | context: §6.4 Segmentation Evaluation
- [PENDING] Segmentation confusion matrix: same run. Result file: `evaluation/results/segmentation_confusion_matrix.png` | file: ch06-testing-evaluation.md | context: §6.4 Segmentation Evaluation — Figure 7
- [PENDING] Elasticity MAE/RMSE/Pearson/Spearman/sign_agreement vs `true_elasticity`: run `python evaluation/run_evaluation.py --only elasticity` with GT DB reachable. Result file: `evaluation/results/elasticity_metrics.json` (GT fields) | file: ch06-testing-evaluation.md | context: §6.5 Elasticity Evaluation
- [PENDING] Elasticity by-category breakdown: same run. Result file: `evaluation/results/elasticity_by_category.csv` | file: ch06-testing-evaluation.md | context: §6.5 Elasticity Evaluation
- [PENDING] Pricing constraint compliance (violation count): run `python evaluation/run_evaluation.py --only pricing` with DB reachable. Result file: `evaluation/results/pricing_constraint_compliance.json` | file: ch06-testing-evaluation.md | context: §6.6 Pricing Evaluation
- [PENDING] Pricing direction distribution (INCREASE/DECREASE/KEEP counts): same run. Result file: `evaluation/results/pricing_direction_distribution.json` | file: ch06-testing-evaluation.md | context: §6.6 Pricing Evaluation
- [PENDING] Pricing elasticity-direction correlation (Pearson): same run. Result file: `evaluation/results/pricing_elasticity_direction_correlation.json` | file: ch06-testing-evaluation.md | context: §6.6 Pricing Evaluation
- [PENDING] LLM guardrail stored pass rate: run evaluation with DB reachable (requires stored explanations in `llm_explanation` table). Result file: `evaluation/results/llm_guardrail_stored_pass_rate.json` | file: ch06-testing-evaluation.md | context: §6.6 LLM Evaluation
- [PENDING] LLM numeric consistency check: run `python evaluation/run_evaluation.py --with-llm` with valid `LLM_API_KEY` in `.env`. Result file: `evaluation/results/llm_numeric_consistency.json` | file: ch06-testing-evaluation.md | context: §6.6 LLM Evaluation
- [PENDING] Abstract update: once the above evaluation metrics are available, update the Abstract (front-matter.md §Abstract) to replace the `[PENDING: ...]` clause with the measured result | file: front-matter.md | context: Abstract — final sentence

---

## appendices.md

### TEAM TO FILL / TEAM TO CONFIRM

- [TEAM TO CONFIRM] Appendix F, item 3 — confirm whether M5 validation was listed as a required deliverable in the approved synopsis or SRS | file: appendices.md | context: Appendix F §3 — M5 dataset validation
- [TEAM TO FILL] Appendix F — attach approved synopsis and SRS; list any additional deviations not covered by items 1–3 | file: appendices.md | context: Appendix F — Deviations from Synopsis and SRS
- [TEAM TO FILL] Appendix G — Team Contributions table: three rows with Team Member, Phases Led, Modules Implemented, Tests Written, Report Sections Written | file: appendices.md | context: Appendix G

---

## references.md

### CITATION NEEDED — Software version fields (RESOLVED)

The following software versions have been filled in from `requirements.txt` and `package.json`:

- scikit-learn: **1.5.2** (`data-pipeline/requirements.txt`) ✅
- XGBoost: **2.1.3** (`data-pipeline/requirements.txt`) ✅
- statsmodels: **not used** — elasticity uses hand-coded NumPy OLS in `pricing/elasticity_model.py`; reference entry 15 should be removed ✅
- Flask: **3.1.0** (`backend/requirements.txt`) ✅
- Chart.js: **4.5.1** (`frontend/package.json`) ✅

Remaining in references.md:
- [CITATION NEEDED] All 11 academic reference details (editions, journal volumes, page numbers, DOIs) — listed in ch02-literature-review.md section above

---

## Pending Screenshots

The following screenshots must be captured with the live system running. See `docs/report/figure-and-screenshot-list.md` §3 for exact instructions.

- [PENDING SCREENSHOT] Figure 10 — Forecast View, product P001 (Staples, current price ₹3.28, low elasticity). Save to: `docs/report/figures/screenshots/forecast-p001.png`
- [PENDING SCREENSHOT] Figure 11 — Forecast View, product P042 (Impulse, high elasticity). Save to: `docs/report/figures/screenshots/forecast-p042.png`
- [PENDING SCREENSHOT] Figure 12 — Segments View (stat tiles, segment table, revenue doughnut chart). Save to: `docs/report/figures/screenshots/segments.png`
- [PENDING SCREENSHOT] Figure 13 — Pricing View, product P001 (₹3.28 → ₹3.77, binding constraint MAX_CHANGE). Save to: `docs/report/figures/screenshots/pricing-p001.png`
- [PENDING SCREENSHOT] Figure 14 — Pricing View, product P023 (Electronics, DECREASE recommendation). Save to: `docs/report/figures/screenshots/pricing-p023.png`
- [PENDING SCREENSHOT] Figure 15 — Pricing View, product P027 (MARGIN binding constraint). Save to: `docs/report/figures/screenshots/pricing-p027.png`

---

## Diagrams Needing Manual Export

The following Mermaid source files must be exported to PNG via [https://mermaid.live](https://mermaid.live) before assembling the final report. See `docs/report/figure-and-screenshot-list.md` §1 for export instructions.

- Figure 1 — `docs/report/diagrams/architecture.mmd` → export to `docs/report/diagrams/architecture.png`
- Figure 2 — `docs/report/diagrams/data-flow.mmd` → export to `docs/report/diagrams/data-flow.png`
- Figure 3 — `docs/report/diagrams/er-diagram.mmd` → export to `docs/report/diagrams/er-diagram.png`
- Figure 4 — `docs/report/diagrams/pricing-flow.mmd` → export to `docs/report/diagrams/pricing-flow.png`
- Figure 5 — `docs/report/diagrams/dataset-generation.mmd` → export to `docs/report/diagrams/dataset-generation.png`

---

## Corrections Made During Consistency Pass

The following discrepancies were found between documentation files and the code during the investigation step. Corrections have been noted where they affect report content.

- **DISC-01 (Pricing direction counts)**: `docs/results.md` states raised/cut/kept = 15/32/3 and explicitly flags these as produced with the Linear Regression model. `docs/viva-guide.md` states 34/13/3 (no model qualifier; likely the XGBoost run). The report uses the viva-guide numbers (34/13/3) as the XGBoost-based figures. Team should re-run `python -m pricing.run_pricing` with XGBoost to confirm.
- **DISC-02 (Test counts)**: `README.md` states 56 pipeline tests and 86 backend tests. `docs/test-report.md` states 65 and 87 respectively (Phase 13 added 9 + 1 tests). The report uses test-report.md counts (65 / 87 / 76). README should be updated to match.
- **DISC-03 (TIE_TOLERANCE missing from api.md)**: `docs/api.md` does not list `TIE_TOLERANCE` as a valid `binding_constraint` value; 7 products (P013, P015, P016, P018, P021, P022, P030) have this value in the database. Listed as KI-01 in `docs/known-issues.md`. Added to Appendix B for completeness.
- **DISC-04 (Elasticity and segmentation GT metrics sourced from Phase 7)**: Elasticity MAE=0.062, RMSE=0.091, correlation=0.990 and ARI=1.0 are from `docs/results.md` (Phase 7 run, GT DB was available). These are not in `evaluation/results/` (GT DB was unavailable in Phase 13). The report cites these as Phase 7 results, not Phase 13.
- **DISC-05 (Python 3.13 used in evaluation)**: `evaluation/results/evaluation_summary.json` shows Python 3.13 was used; `README.md` explicitly states 3.13 is not supported. This may have contributed to the XGBoost load failure. Noted in Chapter 6 threats-to-validity.
- **DISC-06 (Candidate count arithmetic)**: `docs/results.md` reports 1 225 passing candidates and 235 + 122 rejections (total 1 582 ≠ 1 550). The arithmetic discrepancy arises because a candidate can fail multiple constraints simultaneously and be counted twice in the rejection tallies. Authoritative total: 1 550 candidates (50 products × 31 price steps = 50 × (30 steps ± 15% at 1% resolution + current price)).

---

## Summary counts

- TEAM TO FILL: 18 items
- TEAM TO CONFIRM: 5 items
- CITATION NEEDED: 11 items (11 academic — software versions resolved ✅)
- PENDING evaluation: 16 items (all resolve by re-running `evaluation/run_evaluation.py` with live DB and working XGBoost)
- Pending screenshots: 6 items (Figures 10–15)
- Diagrams to export: 5 items (architecture.mmd, data-flow.mmd, er-diagram.mmd, pricing-flow.mmd, dataset-generation.mmd)

**Total remaining items: 61** (was 67; 6 software version citations resolved)
