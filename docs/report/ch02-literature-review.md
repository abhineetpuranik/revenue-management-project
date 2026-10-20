# Chapter 2 — Literature Review

## 2.1 Demand Forecasting in Retail

Demand forecasting in retail has a long history, beginning with classical statistical approaches such as autoregressive integrated moving average (ARIMA) models and exponential smoothing families (e.g., Holt-Winters). These methods remain competitive on short, univariate series and are still widely used in practice. [CITATION NEEDED: Hyndman and Athanasopoulos, *Forecasting: Principles and Practice*, 3rd edition, 2021 — comprehensive treatment of statistical forecasting methods including ARIMA and exponential smoothing.]

The availability of large transaction datasets and the maturation of gradient-boosted tree libraries shifted attention towards machine learning approaches in the 2010s. Gradient-boosted decision trees, in particular XGBoost [CITATION NEEDED: Chen and Guestrin, *XGBoost: A Scalable Tree Boosting System*, KDD 2016 — original XGBoost paper], are now among the most widely used methods in retail forecasting competitions and production systems. They handle heterogeneous tabular features naturally (lag features, calendar features, price features), are robust to missing values, and train quickly on a single machine. The M5 Accuracy Competition [CITATION NEEDED: Makridakis, Spiliotis, and Assimakopoulos, *M5 accuracy competition: Results, findings, and conclusions*, International Journal of Forecasting, 2022 — benchmark comparing statistical and ML forecasting methods at scale] confirmed that gradient-boosted tree ensembles, often combined with lag and calendar features, achieve state-of-the-art accuracy on large-scale retail hierarchies.

More recently, deep learning models — recurrent networks (LSTM), attention-based models (Temporal Fusion Transformer), and large foundation models pre-trained on time-series data — have been applied to demand forecasting. These methods can learn complex temporal dependencies and cross-series patterns that tree models cannot capture directly. [CITATION NEEDED: Lim, Arik, Loeff, and Pfister, *Temporal Fusion Transformers for interpretable multi-horizon time series forecasting*, International Journal of Forecasting, 2021 — representative deep learning forecasting paper.]

This project uses machine learning (XGBoost as the primary model, Ridge regression as a baseline) and deliberately excludes deep learning. The justification is one of scope: deep sequence models require substantially more data, more hyperparameter tuning effort, and more infrastructure (GPU or extended CPU training time) than is appropriate for a proof-of-concept on 50 products. The exclusion is revisited as a future direction in Chapter 7.

## 2.2 Customer Segmentation

Customer segmentation is a standard technique in retail marketing analytics. Dividing a customer base into groups with similar purchasing behaviour allows a retailer to tailor promotions, retention campaigns, and communication strategies to each group.

Recency–Frequency–Monetary (RFM) analysis is one of the most widely adopted segmentation frameworks in retail. It characterises each customer along three dimensions: how recently they made a purchase (Recency), how often they purchase (Frequency), and how much they spend in total (Monetary value). [CITATION NEEDED: Hughes, *Strategic Database Marketing*, 1994 (or the 1996 journal article — *Boosting Response with RFM*) — original or early formalisation of the RFM framework.]

RFM scores are continuous-valued features, and K-Means clustering [CITATION NEEDED: Kaufman and Rousseeuw, *Finding Groups in Data: An Introduction to Cluster Analysis*, Wiley, 1990 — foundational cluster analysis textbook; or the original Lloyd K-Means paper, Lloyd 1982] provides a natural way to group customers by their position in the three-dimensional RFM space. K-Means partitions customers into k clusters by minimising within-cluster squared Euclidean distance; it is computationally efficient, interpretable, and widely used in practice.

The choice of k is typically guided by the elbow method (plotting within-cluster inertia against k and identifying the point at which marginal improvements diminish) and the silhouette coefficient [CITATION NEEDED: Rousseeuw, *Silhouettes: A graphical aid to the interpretation and validation of cluster analysis*, Journal of Computational and Applied Mathematics, 1987 — original silhouette paper]. The silhouette coefficient for a data point measures how similar it is to its own cluster relative to the nearest other cluster, with a score of 1 indicating perfect assignment. This project uses both criteria: k is searched from 2 to 10, and k=4 is selected because silhouette peaks at 0.8573 (source: `evaluation/results/segmentation_k_search.csv`), which is also consistent with the four known generative segments.

## 2.3 Price Elasticity Estimation

Price elasticity of demand measures the percentage change in quantity demanded resulting from a one-percent change in price. Formally, the constant elasticity model is expressed in log-log form:

```
log(Q) = α + β·log(P) + controls + ε
```

where β is the elasticity coefficient, α is an intercept, controls capture confounds such as promotions and seasonality, and ε is an error term. Ordinary least squares (OLS) estimation of this model is a standard approach in econometrics and retail analytics. [CITATION NEEDED: Varian, *Intermediate Microeconomics: A Modern Approach*, 9th edition, W.W. Norton, 2014 — or an equivalent econometrics text (e.g., Wooldridge, *Introductory Econometrics*, 2019) covering price elasticity and log-log OLS.]

A well-known challenge in estimating price elasticity from observational retail data is endogeneity: if retailers raise prices when demand is high (e.g., ahead of a festival), the observed correlation between price and quantity understates the true negative elasticity. Addressing endogeneity typically requires instrumental variables or randomised price experiments. In this project, the synthetic data are generated by a process in which prices change on a fixed schedule with a known random component that is independent of demand shocks, so endogeneity does not arise. The OLS estimates are therefore unbiased by construction, which makes the synthetic setting particularly clean for validating the estimation approach.

## 2.4 Dynamic Pricing and Revenue Management

Classical revenue management originated in the airline industry as yield management: the practice of selling the same seat at different prices to different customer segments to maximise total revenue from a fixed capacity. The theoretical foundations are covered in the reference text by Talluri and van Ryzin. [CITATION NEEDED: Talluri and van Ryzin, *The Theory and Practice of Revenue Management*, Springer, 2004 — standard reference text on revenue management.]

Modern ML approaches frame dynamic pricing as a prediction problem: forecast demand at each candidate price, and select the price that maximises expected revenue subject to business constraints. This is the approach implemented in this project. The pricing optimiser generates a discrete grid of candidate prices (±15% from the current price in 1% steps; source: `data-pipeline/pricing/pricing_config.py`), estimates expected demand at each candidate using the XGBoost baseline demand scaled by the elasticity ratio, and selects the revenue-maximising candidate that passes all constraints.

Reinforcement learning (RL) offers a more sophisticated framing: an agent interacts with the environment (customers) repeatedly, observing demand responses and updating its pricing policy to maximise long-run cumulative revenue. [CITATION NEEDED: Sutton and Barto, *Reinforcement Learning: An Introduction*, 2nd edition, MIT Press, 2018 — standard RL textbook.] [CITATION NEEDED: a representative paper on RL for dynamic retail pricing, e.g., Raju and Roy, or a more recent survey such as den Boer, *Dynamic pricing and learning: Historical origins, current research, and new directions*, Surveys in Operations Research and Management Science, 2015 — or a recent deep RL pricing paper.]

This project does not implement reinforcement learning. The pricing module is a one-shot optimiser: it computes a recommendation at a single point in time using stored forecasts and elasticity estimates, without an exploration–exploitation mechanism or environment interaction. RL is identified as a future direction in Chapter 7.

## 2.5 Commercial Tools and Their Gaps

Several commercial platforms address demand forecasting and dynamic pricing for retail. Enterprise systems such as Oracle Retail Demand Forecasting, Salesforce Commerce Cloud, and specialised SaaS pricing tools (e.g., Revionics, Competera) offer sophisticated forecasting, segmentation, and pricing capabilities, but they are designed for large retailers with substantial data infrastructure, technical staff, and budgets for licensing and integration.

For SMEs — a retailer with tens of products, a small transaction database, and no dedicated data science team — these platforms are typically inaccessible. The barrier is not primarily technical but economic: the cost of licensing, implementation, and ongoing support exceeds what most small retailers can justify. Open-source alternatives exist for individual components (scikit-learn for clustering, XGBoost for tree models, statsmodels for OLS regression) but are not integrated into end-to-end pipelines with a retail-facing user interface and plain-English output.

This project addresses the gap by combining open-source components into a self-hosted proof-of-concept pipeline with a REST API and a web dashboard, designed to run on a single developer machine without enterprise infrastructure.

## 2.6 Summary and Positioning

This project applies well-established methods — XGBoost for demand forecasting, K-Means on RFM features for customer segmentation, and log-log OLS regression for price elasticity estimation — to a synthetic retail dataset as a proof-of-concept. It does not claim to outperform commercial pricing tools, to validate on real retail data, or to implement the state-of-the-art methods described in the forecasting and RL literature. Its contribution is an integrated, open-source, end-to-end pipeline with a full evaluation layer that measures model recovery of known synthetic structure, and an LLM explanation interface that makes the outputs accessible to non-technical users. The methods chosen are deliberately simple and reproducible; the exclusion of deep learning and reinforcement learning is a deliberate scope decision rather than an oversight.
