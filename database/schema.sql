-- =============================================================================
-- Revenue Management — Full Database Schema
-- Phase 2b: replaces the Phase 0 placeholder with real DDL.
--
-- Two schemas are created:
--   revenue_management     — application schema (used by the Flask API,
--                            feature engineering, forecasting, pricing).
--   revenue_management_gt  — ground-truth holdout schema (used ONLY by
--                            Phase 6/7 evaluation code; NEVER joined into
--                            normal application queries).
--
-- Ground-truth separation rationale
-- ----------------------------------
-- The Phase 1a generator attached true_elasticity to each product and
-- true_segment (plus buying-behaviour parameters) to each customer so that
-- the downstream ML modules (Phase 6 segmentation, Phase 7 elasticity
-- estimation) can be evaluated against known-correct answers.  Keeping these
-- columns in the application schema would risk a developer accidentally
-- including them as model features, which would make evaluation meaningless.
-- Placing them in a physically separate schema means a normal app query
-- (which only connects to DB_NAME = revenue_management) cannot reach them
-- even if someone forgets — a cross-schema JOIN must be deliberate.
--
-- Run instructions
-- ----------------
--   mysql -u <user> -p < schema.sql
-- or paste into MySQL Workbench / DBeaver.
-- The script is idempotent: it drops and recreates both schemas each time.
-- =============================================================================


-- ============================================================
-- 0. Schema creation
-- ============================================================

DROP SCHEMA IF EXISTS revenue_management_gt;
DROP SCHEMA IF EXISTS revenue_management;

CREATE SCHEMA revenue_management
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

CREATE SCHEMA revenue_management_gt
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE revenue_management;


-- ============================================================
-- 1. Dimension tables (no FK dependencies)
-- ============================================================

-- ------------------------------------------------------------
-- 1a. product
-- Note: true_elasticity is intentionally ABSENT here.
--       It lives in revenue_management_gt.gt_product_elasticity.
-- ------------------------------------------------------------
CREATE TABLE product (
    product_id   VARCHAR(10)    NOT NULL,
    category     VARCHAR(30)    NOT NULL,
    base_price   DECIMAL(10,2)  NOT NULL,   -- £ price at generation time
    base_demand  INT            NOT NULL,   -- avg units/day at base_price

    CONSTRAINT pk_product PRIMARY KEY (product_id)
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 1b. customer
-- Note: true_segment and buying-behaviour params are intentionally
--       ABSENT here.  They live in revenue_management_gt.gt_customer_segment.
-- ------------------------------------------------------------
CREATE TABLE customer (
    customer_id  VARCHAR(10)    NOT NULL,

    CONSTRAINT pk_customer PRIMARY KEY (customer_id)
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 1c. calendar
-- ------------------------------------------------------------
CREATE TABLE calendar (
    date              DATE           NOT NULL,
    year              SMALLINT       NOT NULL,
    month             TINYINT        NOT NULL,   -- 1–12
    weekday           TINYINT        NOT NULL,   -- 0=Mon … 6=Sun
    weekday_name      VARCHAR(10)    NOT NULL,
    is_weekend        TINYINT(1)     NOT NULL,   -- 0/1 boolean
    seasonal_factor   DECIMAL(6,4)   NOT NULL,
    weekday_factor    DECIMAL(6,4)   NOT NULL,
    combined_factor   DECIMAL(6,4)   NOT NULL,   -- seasonal × weekday
    festival_flag     TINYINT(1)     NOT NULL,   -- 1 on selected dates

    CONSTRAINT pk_calendar PRIMARY KEY (date)
) ENGINE=InnoDB;


-- ============================================================
-- 2. Transactional / fact tables (depend on dimension tables)
-- ============================================================

-- ------------------------------------------------------------
-- 2a. price  — one row per (product, date); price history
-- ------------------------------------------------------------
CREATE TABLE price (
    product_id    VARCHAR(10)    NOT NULL,
    date          DATE           NOT NULL,
    price         DECIMAL(10,2)  NOT NULL,
    is_promo      TINYINT(1)     NOT NULL DEFAULT 0,
    discount_pct  DECIMAL(6,4)   NOT NULL DEFAULT 0.0000,

    CONSTRAINT pk_price       PRIMARY KEY (product_id, date),
    CONSTRAINT fk_price_prod  FOREIGN KEY (product_id) REFERENCES product(product_id),
    CONSTRAINT fk_price_cal   FOREIGN KEY (date)       REFERENCES calendar(date)
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 2b. stock  — daily end-of-day stock level per product
-- ------------------------------------------------------------
CREATE TABLE stock (
    product_id       VARCHAR(10)  NOT NULL,
    date             DATE         NOT NULL,
    stock_level      INT          NOT NULL DEFAULT 0,
    units_restocked  INT          NOT NULL DEFAULT 0,
    stockout_flag    TINYINT(1)   NOT NULL DEFAULT 0,

    CONSTRAINT pk_stock       PRIMARY KEY (product_id, date),
    CONSTRAINT fk_stock_prod  FOREIGN KEY (product_id) REFERENCES product(product_id),
    CONSTRAINT fk_stock_cal   FOREIGN KEY (date)       REFERENCES calendar(date)
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 2c. sales  — central fact table; one row per customer transaction
-- ------------------------------------------------------------
CREATE TABLE sales (
    sale_id        INT            NOT NULL,   -- surrogate from CSV (1-based)
    customer_id    VARCHAR(10)    NOT NULL,
    product_id     VARCHAR(10)    NOT NULL,
    date           DATE           NOT NULL,
    units_sold     INT            NOT NULL,
    price_at_sale  DECIMAL(10,2)  NOT NULL,
    discount_pct   DECIMAL(6,4)   NOT NULL DEFAULT 0.0000,
    revenue        DECIMAL(12,2)  NOT NULL,

    CONSTRAINT pk_sales        PRIMARY KEY (sale_id),
    CONSTRAINT fk_sales_cust   FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    CONSTRAINT fk_sales_prod   FOREIGN KEY (product_id)  REFERENCES product(product_id),
    CONSTRAINT fk_sales_cal    FOREIGN KEY (date)        REFERENCES calendar(date),

    -- Most common query patterns for forecasting and segmentation
    INDEX idx_sales_product_date  (product_id, date),
    INDEX idx_sales_customer      (customer_id),
    -- Supporting index for date-range scans
    INDEX idx_sales_date          (date)
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 2d. customer_rfm_segment  — Phase 6 (segmentation/run_segmentation.py)
--     RFM values + K-Means cluster + business label per customer.
--     Also created at run time (CREATE TABLE IF NOT EXISTS).
-- ------------------------------------------------------------
CREATE TABLE customer_rfm_segment (
    customer_id     VARCHAR(10)    NOT NULL,
    recency_days    INT            NOT NULL,
    frequency       INT            NOT NULL,   -- distinct purchase dates
    monetary        DECIMAL(14,2)  NOT NULL,   -- total revenue
    cluster_id      INT            NOT NULL,
    segment_label   VARCHAR(20)    NOT NULL,   -- high_value|regular|occasional|at_risk
    assigned_at     DATETIME       NOT NULL,
    CONSTRAINT pk_customer_rfm_segment PRIMARY KEY (customer_id),
    CONSTRAINT fk_rfm_segment_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    INDEX idx_rfm_segment_label (segment_label)
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 2e. segment_summary  — Phase 6; one row per segment label.
--     Structured input for the Phase 9 LLM explanations.
-- ------------------------------------------------------------
CREATE TABLE segment_summary (
    segment_label        VARCHAR(20)    NOT NULL,
    customer_count       INT            NOT NULL,
    share_pct            DECIMAL(6,2)   NOT NULL,
    mean_recency_days    DECIMAL(10,2)  NOT NULL,
    median_recency_days  DECIMAL(10,2)  NOT NULL,
    mean_frequency       DECIMAL(10,2)  NOT NULL,
    median_frequency     DECIMAL(10,2)  NOT NULL,
    mean_monetary        DECIMAL(14,2)  NOT NULL,
    median_monetary      DECIMAL(14,2)  NOT NULL,
    total_revenue        DECIMAL(16,2)  NOT NULL,
    revenue_share_pct    DECIMAL(6,2)   NOT NULL,
    assigned_at          DATETIME       NOT NULL,
    CONSTRAINT pk_segment_summary PRIMARY KEY (segment_label)
) ENGINE=InnoDB;

-- ============================================================
-- 3. Ground-truth holdout schema
--    IMPORTANT: these tables must NEVER be joined in application
--    queries or used as ML training features.
-- ============================================================

USE revenue_management_gt;

-- ------------------------------------------------------------
-- 3a. gt_product_elasticity
--     true_elasticity: known price-elasticity of demand per
--     product.  Used in Phase 7 to evaluate estimated elasticity.
-- ------------------------------------------------------------
CREATE TABLE gt_product_elasticity (
    product_id       VARCHAR(10)   NOT NULL,
    true_elasticity  DECIMAL(8,4)  NOT NULL,   -- range -2.54 .. -0.10; negative

    CONSTRAINT pk_gt_prod PRIMARY KEY (product_id)
) ENGINE=InnoDB;


-- ------------------------------------------------------------
-- 3b. gt_customer_segment
--     true_segment and buying-behaviour parameters per customer.
--     Used in Phase 6 to evaluate segmentation model output.
--     purchase_rate / basket_mean / basket_std are the simulation
--     parameters — they are ground truth, not observable features.
-- ------------------------------------------------------------
CREATE TABLE gt_customer_segment (
    customer_id    VARCHAR(10)   NOT NULL,
    true_segment   VARCHAR(20)   NOT NULL,  -- high_value|regular|occasional|at_risk
    purchase_rate  DECIMAL(5,3)  NOT NULL,  -- expected purchases/day
    basket_mean    DECIMAL(8,2)  NOT NULL,  -- mean spend per transaction (£)
    basket_std     DECIMAL(8,2)  NOT NULL,  -- std of spend per transaction (£)

    CONSTRAINT pk_gt_cust PRIMARY KEY (customer_id)
) ENGINE=InnoDB;


-- ============================================================
-- 4. Model output tables (application schema)
--    Created by the pipeline modules at run time as well
--    (CREATE TABLE IF NOT EXISTS), so they survive without
--    re-running this file. Kept here as the documented design.
-- ============================================================

USE revenue_management;

-- ------------------------------------------------------------
-- 4a. product_elasticity  — Phase 7 (pricing/estimate_elasticity.py)
--     One log-log OLS estimate per product. reliable_flag = 0
--     means Phase 8 must not move that product's price.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS product_elasticity (
    product_id          VARCHAR(10)   NOT NULL,
    category            VARCHAR(30)   NOT NULL,
    elasticity          DECIMAL(8,4)  NULL,
    std_error           DECIMAL(8,4)  NULL,
    ci_low              DECIMAL(8,4)  NULL,
    ci_high             DECIMAL(8,4)  NULL,
    r_squared           DECIMAL(6,4)  NULL,
    n_obs               INT           NOT NULL,
    reliable_flag       TINYINT(1)    NOT NULL,
    unreliable_reasons  VARCHAR(100)  NOT NULL DEFAULT '',
    estimated_at        DATETIME      NOT NULL,
    CONSTRAINT pk_product_elasticity PRIMARY KEY (product_id),
    CONSTRAINT fk_elasticity_product FOREIGN KEY (product_id) REFERENCES product(product_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4b. pricing_candidates  — Phase 8a (pricing/build_candidates.py)
--     Every candidate price per product, INCLUDING rejected ones,
--     with the reason codes it failed (MARGIN, MAX_CHANGE,
--     PRICE_RANGE, ELASTICITY_UNRELIABLE). step = % step from
--     the current price (0 = current price).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pricing_candidates (
    product_id       VARCHAR(10)    NOT NULL,
    step             INT            NOT NULL,
    candidate_price  DECIMAL(10,2)  NOT NULL,
    change_pct       DECIMAL(8,4)   NOT NULL,
    unit_cost        DECIMAL(10,4)  NOT NULL,   -- ASSUMED: base_price x COST_RATIO[category]
    margin_pct       DECIMAL(8,4)   NOT NULL,
    is_current       TINYINT(1)     NOT NULL,
    passes_all       TINYINT(1)     NOT NULL,
    failed_reasons   VARCHAR(100)   NOT NULL DEFAULT '',
    CONSTRAINT pk_pricing_candidates PRIMARY KEY (product_id, step),
    CONSTRAINT fk_candidates_product FOREIGN KEY (product_id) REFERENCES product(product_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4c. pricing_recommendation  — Phase 8b (pricing/run_pricing.py)
--     One revenue-maximising price per product for the forecast
--     week, with expected impact and the constraint that stopped it.
--     binding_constraint: MAX_CHANGE | MARGIN | PRICE_RANGE |
--       STOCK | TIE_TOLERANCE | NONE | NO_FEASIBLE_PRICE
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pricing_recommendation (
    product_id          VARCHAR(10)    NOT NULL,
    category            VARCHAR(30)    NOT NULL,
    current_price       DECIMAL(10,2)  NOT NULL,
    recommended_price   DECIMAL(10,2)  NOT NULL,
    change_pct          DECIMAL(8,4)   NOT NULL,
    elasticity          DECIMAL(8,4)   NOT NULL,
    baseline_demand     DECIMAL(12,2)  NOT NULL,   -- Phase 5 forecast at the current price
    expected_demand     DECIMAL(12,2)  NOT NULL,   -- at the recommended price
    available_stock     INT            NOT NULL,
    current_revenue     DECIMAL(14,2)  NOT NULL,
    expected_revenue    DECIMAL(14,2)  NOT NULL,
    revenue_change_pct  DECIMAL(8,4)   NOT NULL,
    unit_cost           DECIMAL(10,4)  NOT NULL,   -- ASSUMED cost (see pricing_config.py)
    margin_pct          DECIMAL(8,4)   NOT NULL,
    expected_profit     DECIMAL(14,2)  NOT NULL,
    stock_limited       TINYINT(1)     NOT NULL,
    binding_constraint  VARCHAR(30)    NOT NULL,
    reason_codes        VARCHAR(100)   NOT NULL DEFAULT '',
    model_type          VARCHAR(30)    NOT NULL,
    forecast_week       VARCHAR(10)    NOT NULL,   -- e.g. 2025-W01
    generated_at        DATETIME       NOT NULL,
    CONSTRAINT pk_pricing_recommendation PRIMARY KEY (product_id),
    CONSTRAINT fk_recommendation_product FOREIGN KEY (product_id) REFERENCES product(product_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4d. llm_explanation  — Phase 9 (explanations/generate_explanations.py)
--     One plain-English sentence per pricing recommendation and per
--     customer segment. source = llm | fallback (template used when
--     the LLM failed or its output was rejected by the guardrails).
--     payload_json is exactly what the LLM saw; payload_hash drives
--     the cache (unchanged payload + model => no new API call).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_explanation (
    explanation_id    INT            NOT NULL,
    entity_type       VARCHAR(10)    NOT NULL,   -- pricing | segment
    entity_id         VARCHAR(20)    NOT NULL,   -- product_id or segment_label
    explanation_text  VARCHAR(1000)  NOT NULL,
    source            VARCHAR(10)    NOT NULL,   -- llm | fallback
    payload_json      TEXT           NOT NULL,
    payload_hash      CHAR(64)       NOT NULL,
    model_name        VARCHAR(60)    NOT NULL,
    guardrail_status  VARCHAR(10)    NOT NULL,   -- passed | fallback
    rejection_reason  VARCHAR(255)   NOT NULL DEFAULT '',
    attempts          INT            NOT NULL,
    generated_at      DATETIME       NOT NULL,
    CONSTRAINT pk_llm_explanation PRIMARY KEY (explanation_id),
    CONSTRAINT uq_llm_explanation_entity UNIQUE (entity_type, entity_id)
) ENGINE=InnoDB;

-- ============================================================
-- End of schema
-- ============================================================
