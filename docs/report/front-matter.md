# Front Matter

---

## Title Page

**[TEAM TO FILL: project title — suggested: 'AI-Powered Demand Forecasting and Dynamic Pricing for Retail Businesses']**

A Final-Year Undergraduate Project Report

Submitted in partial fulfilment of the requirements for the degree of

[TEAM TO FILL: degree title, e.g. Bachelor of Engineering / Bachelor of Technology in Computer Science and Engineering]

by

| Student Name | Roll Number |
|---|---|
| [TEAM TO FILL: Student 1 full name] | [TEAM TO FILL: Roll No. 1] |
| [TEAM TO FILL: Student 2 full name] | [TEAM TO FILL: Roll No. 2] |
| [TEAM TO FILL: Student 3 full name] | [TEAM TO FILL: Roll No. 3] |

Under the supervision of

**[TEAM TO FILL: supervisor name and designation]**

**[TEAM TO FILL: department name]**

**[TEAM TO FILL: institution name]**

**[TEAM TO FILL: submission month and year, e.g. May 2025]**

---

## Certificate of Originality

This is to certify that the project report entitled **[TEAM TO FILL: project title]**, submitted by [TEAM TO FILL: Student 1 name], [TEAM TO FILL: Student 2 name], and [TEAM TO FILL: Student 3 name] to [TEAM TO FILL: institution name] in partial fulfilment of the requirements for the award of the degree of [TEAM TO FILL: degree title], is a record of bonafide project work carried out by them under my supervision and guidance.

The contents of this report have not been submitted and will not be submitted either in part or in full for the award of any other degree or diploma at this or any other institution.

**Supervisor:**

Signature: ________________________

Name: [TEAM TO FILL: supervisor name]

Designation: [TEAM TO FILL: supervisor designation]

Date: [TEAM TO FILL: date]

---

## Declaration

We, [TEAM TO FILL: Student 1 name], [TEAM TO FILL: Student 2 name], and [TEAM TO FILL: Student 3 name], hereby declare that the project report entitled **[TEAM TO FILL: project title]**, submitted to [TEAM TO FILL: institution name] in partial fulfilment of the requirements for the award of the degree of [TEAM TO FILL: degree title], is a record of original work carried out by us.

We further declare that this report has not been submitted, either in part or in full, for any other degree or diploma at this or any other institution.

**Student 1:**

Signature: ________________________

Name: [TEAM TO FILL: Student 1 full name]

Roll No.: [TEAM TO FILL: Roll No. 1]

Date: [TEAM TO FILL: date]

**Student 2:**

Signature: ________________________

Name: [TEAM TO FILL: Student 2 full name]

Roll No.: [TEAM TO FILL: Roll No. 2]

Date: [TEAM TO FILL: date]

**Student 3:**

Signature: ________________________

Name: [TEAM TO FILL: Student 3 full name]

Roll No.: [TEAM TO FILL: Roll No. 3]

Date: [TEAM TO FILL: date]

---

## Acknowledgement

[TEAM TO FILL: write your acknowledgements here. Suggested content: express gratitude to your supervisor for their guidance; thank the department for providing infrastructure; acknowledge any open-source libraries or datasets used; include a personal note from the team if appropriate.]

---

## Abstract

Retail small and medium-sized enterprises (SMEs) face persistent challenges in managing product demand, customer behaviour, and pricing decisions without access to dedicated analytics infrastructure. This project addresses those challenges by designing and implementing an end-to-end, AI-powered revenue management system capable of forecasting weekly product demand, segmenting customers by purchase behaviour, estimating product-level price elasticity, and recommending revenue-maximising prices.

The system is organised as a seven-module data pipeline — synthetic dataset generation, ETL, feature engineering, demand forecasting, customer segmentation, price elasticity estimation, and pricing optimisation — together with a large language model (LLM) explanation layer, a Flask REST API, and an Angular web dashboard. The dataset is fully synthetic, comprising 50 products, 1,000 customers, and three years of daily sales data (approximately 1.3 million transaction rows), generated from a known parametric ground truth; all results therefore demonstrate the ability of the models to recover structure embedded in the data and do not constitute evidence of real-world retail performance.

Demand forecasting is performed by an XGBoost model and a Linear Regression baseline. The XGBoost model achieved a mean absolute percentage error (MAPE) of 9.72% on the held-out eight-week test window, compared with 15.26% for Linear Regression (source: `data-pipeline/models/artifacts/metadata.json`). Customer segmentation uses k-means clustering applied to recency-frequency-monetary (RFM) features; the optimal cluster count of four was selected by silhouette score, which peaked at 0.8573, and the solution was perfectly stable across five random seeds (ARI = 1.0) (source: `evaluation/results/segmentation_k_search.csv`, `evaluation/results/segmentation_stability.json`). Price elasticity is estimated by product-level ordinary least squares (OLS) log-log regression; all 50 estimated elasticities were negative, with a mean of −1.3562 (source: `evaluation/results/elasticity_metrics.json`). The LLM explanation layer passed all four failure-handling scenarios and both prompt-validation tests (source: `evaluation/results/llm_failure_handling.json`, `evaluation/results/llm_prompt_validation.json`). Evaluation of pricing constraint compliance and a full forecasting re-run against the live database are [PENDING: run `evaluation/run_evaluation.py` with live DB and working XGBoost environment].

The system is reproducible, deterministic, and fully operational via a REST API and interactive dashboard, demonstrating that a multi-module AI pipeline can be built and evaluated as a single coherent undergraduate project. The principal limitation is the use of synthetic data; generalisation to real retail environments would require empirical validation on observed transaction records.

---

## Table of Contents

- [Front Matter](#front-matter)
  - [Title Page](#title-page)
  - [Certificate of Originality](#certificate-of-originality)
  - [Declaration](#declaration)
  - [Acknowledgement](#acknowledgement)
  - [Abstract](#abstract)
  - [Table of Contents](#table-of-contents)
  - [List of Figures](#list-of-figures)
  - [List of Tables](#list-of-tables)
  - [List of Abbreviations](#list-of-abbreviations)

- [Chapter 1 — Introduction](chapter-01-introduction.md)
  - 1.1 Background
  - 1.2 Problem Statement
  - 1.3 Motivation
  - 1.4 Objectives
  - 1.5 Scope and Limitations
  - 1.6 Summary of Contributions
  - 1.7 Report Organisation

- [Chapter 2 — Literature Review](chapter-02-literature-review.md)
  - 2.1 Demand Forecasting Methods
  - 2.2 Customer Segmentation and RFM Analysis
  - 2.3 Price Elasticity Estimation
  - 2.4 Dynamic Pricing
  - 2.5 Excluded Methods: Reinforcement Learning and Deep Learning
  - 2.6 Existing Commercial Tools and Their Gaps
  - 2.7 Positioning of This Work

- [Chapter 3 — Requirements Analysis](chapter-03-requirements.md)
  - 3.1 User Classes
  - 3.2 Functional Requirements (REQ-1 to REQ-26)
  - 3.3 Non-Functional Requirements
  - 3.4 Constraints
  - 3.5 Traceability Summary

- [Chapter 4 — System Design](chapter-04-design.md)
  - 4.1 System Architecture
  - 4.2 Module Responsibilities and Data Flow
  - 4.3 Database Design
  - 4.4 API Design
  - 4.5 Dashboard Design
  - 4.6 Technology Choices
  - 4.7 Key Design Decisions

- [Chapter 5 — Implementation](chapter-05-implementation.md)
  - 5.1 Synthetic Dataset Generation
  - 5.2 ETL
  - 5.3 Feature Engineering
  - 5.4 Demand Forecasting
  - 5.5 Customer Segmentation
  - 5.6 Price Elasticity Estimation
  - 5.7 Pricing Optimisation
  - 5.8 LLM Explanation Layer
  - 5.9 Flask REST API
  - 5.10 Angular Dashboard

- [Chapter 6 — Testing, Evaluation and Results](chapter-06-evaluation.md)
  - 6.1 Test Strategy
  - 6.2 Test Results
  - 6.3 Evaluation Results — Demand Forecasting
  - 6.4 Evaluation Results — Customer Segmentation
  - 6.5 Evaluation Results — Price Elasticity
  - 6.6 Evaluation Results — Pricing Optimisation
  - 6.7 Evaluation Results — LLM Explanation Layer
  - 6.8 Discussion
  - 6.9 Threats to Validity

- [Chapter 7 — Conclusion and Future Work](chapter-07-conclusion.md)
  - 7.1 Achievement of Objectives
  - 7.2 Limitations
  - 7.3 Future Work

- [References](references.md)

- [Appendix A — Dataset Generation Specification](appendix-a-dataset-spec.md)
- [Appendix B — API Reference Summary](appendix-b-api-reference.md)
- [Appendix C — Setup and User Guide](appendix-c-setup-guide.md)
- [Appendix D — Screenshots](appendix-d-screenshots.md)
- [Appendix E — Full Traceability Matrix](appendix-e-traceability.md)
- [Appendix F — Deviations from Approved Synopsis and SRS](appendix-f-deviations.md)
- [Appendix G — Team Contributions](appendix-g-contributions.md)

---

## List of Figures

*Complete after figures are exported and embedded.*

See [figure-and-screenshot-list.md](figure-and-screenshot-list.md) for the full shot list and export instructions.

---

## List of Tables

The following tables will appear in the main chapters.

### Chapter 3 — Requirements Analysis

- Table 3.1: Functional Requirements Summary (REQ-1 to REQ-26, grouped by feature)
- Table 3.2: Non-Functional Requirements
- Table 3.3: Traceability Summary

### Chapter 4 — System Design

- Table 4.1: Technology Stack
- Table 4.2: Module Responsibilities
- Table 4.3: API Endpoints Summary

### Chapter 5 — Implementation

- Table 5.1: Dataset Generation Parameters (from `config.py`)
- Table 5.2: Elasticity Anchors by Category
- Table 5.3: Customer Segment True Weights
- Table 5.4: Monthly Seasonal Factors
- Table 5.5: Weekday Demand Factors
- Table 5.6: XGBoost Hyperparameters
- Table 5.7: Elasticity Model Parameters
- Table 5.8: Pricing Constraint Parameters

### Chapter 6 — Testing, Evaluation and Results

- Table 6.1: Test Suite Summary (data-pipeline, backend, frontend)
- Table 6.2: Forecasting Model Comparison (MAPE, MAE, RMSE — XGBoost vs Linear Regression)
- Table 6.3: Segmentation k-Search Results (k=2 to k=10, inertia and silhouette)
- Table 6.4: Segmentation Stability (pairwise ARI across 5 seeds)
- Table 6.5: Segmentation RFM Profile by Segment
- Table 6.6: Elasticity Estimates by Category (estimated vs true)
- Table 6.7: LLM Failure Handling Results
- Table 6.8: LLM Prompt Validation Results

---

## List of Abbreviations

| Abbreviation | Definition |
|---|---|
| AI | Artificial Intelligence |
| API | Application Programming Interface |
| ARI | Adjusted Rand Index |
| CSV | Comma-Separated Values |
| DB | Database |
| DDL | Data Definition Language |
| ETL | Extract, Transform, Load |
| GUI | Graphical User Interface |
| HTTP | Hypertext Transfer Protocol |
| JSON | JavaScript Object Notation |
| KPI | Key Performance Indicator |
| LLM | Large Language Model |
| MAE | Mean Absolute Error |
| MAPE | Mean Absolute Percentage Error |
| ML | Machine Learning |
| NMI | Normalised Mutual Information |
| OLS | Ordinary Least Squares |
| RFM | Recency, Frequency, Monetary |
| RMSE | Root Mean Squared Error |
| SME | Small and Medium-sized Enterprise |
| SQL | Structured Query Language |
| UI | User Interface |
| UX | User Experience |
