DROP SCHEMA IF EXISTS revenue_management_gt;
DROP SCHEMA IF EXISTS revenue_management;

CREATE SCHEMA revenue_management
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

CREATE SCHEMA revenue_management_gt
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE revenue_management;

CREATE TABLE product (
    product_id   VARCHAR(10)    NOT NULL,
    category     VARCHAR(30)    NOT NULL,
    base_price   DECIMAL(10,2)  NOT NULL,
    base_demand  INT            NOT NULL,
    CONSTRAINT pk_product PRIMARY KEY (product_id)
) ENGINE=InnoDB;

CREATE TABLE customer (
    customer_id  VARCHAR(10)    NOT NULL,
    CONSTRAINT pk_customer PRIMARY KEY (customer_id)
) ENGINE=InnoDB;

CREATE TABLE calendar (
    date              DATE           NOT NULL,
    year              SMALLINT       NOT NULL,
    month             TINYINT        NOT NULL,
    weekday           TINYINT        NOT NULL,
    weekday_name      VARCHAR(10)    NOT NULL,
    is_weekend        TINYINT(1)     NOT NULL,
    seasonal_factor   DECIMAL(6,4)   NOT NULL,
    weekday_factor    DECIMAL(6,4)   NOT NULL,
    combined_factor   DECIMAL(6,4)   NOT NULL,
    festival_flag     TINYINT(1)     NOT NULL,
    CONSTRAINT pk_calendar PRIMARY KEY (date)
) ENGINE=InnoDB;

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

CREATE TABLE sales (
    sale_id        INT            NOT NULL,
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
    INDEX idx_sales_product_date  (product_id, date),
    INDEX idx_sales_customer      (customer_id),
    INDEX idx_sales_date          (date)
) ENGINE=InnoDB;

CREATE TABLE customer_rfm_segment (
    customer_id     VARCHAR(10)    NOT NULL,
    recency_days    INT            NOT NULL,
    frequency       INT            NOT NULL,
    monetary        DECIMAL(14,2)  NOT NULL,
    cluster_id      INT            NOT NULL,
    segment_label   VARCHAR(20)    NOT NULL,
    assigned_at     DATETIME       NOT NULL,
    CONSTRAINT pk_customer_rfm_segment PRIMARY KEY (customer_id),
    CONSTRAINT fk_rfm_segment_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    INDEX idx_rfm_segment_label (segment_label)
) ENGINE=InnoDB;

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

USE revenue_management_gt;

CREATE TABLE gt_product_elasticity (
    product_id       VARCHAR(10)   NOT NULL,
    true_elasticity  DECIMAL(8,4)  NOT NULL,
    CONSTRAINT pk_gt_prod PRIMARY KEY (product_id)
) ENGINE=InnoDB;

CREATE TABLE gt_customer_segment (
    customer_id    VARCHAR(10)   NOT NULL,
    true_segment   VARCHAR(20)   NOT NULL,
    purchase_rate  DECIMAL(5,3)  NOT NULL,
    basket_mean    DECIMAL(8,2)  NOT NULL,
    basket_std     DECIMAL(8,2)  NOT NULL,
    CONSTRAINT pk_gt_cust PRIMARY KEY (customer_id)
) ENGINE=InnoDB;

USE revenue_management;

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

CREATE TABLE IF NOT EXISTS pricing_candidates (
    product_id       VARCHAR(10)    NOT NULL,
    step             INT            NOT NULL,
    candidate_price  DECIMAL(10,2)  NOT NULL,
    change_pct       DECIMAL(8,4)   NOT NULL,
    unit_cost        DECIMAL(10,4)  NOT NULL,
    margin_pct       DECIMAL(8,4)   NOT NULL,
    is_current       TINYINT(1)     NOT NULL,
    passes_all       TINYINT(1)     NOT NULL,
    failed_reasons   VARCHAR(100)   NOT NULL DEFAULT '',
    CONSTRAINT pk_pricing_candidates PRIMARY KEY (product_id, step),
    CONSTRAINT fk_candidates_product FOREIGN KEY (product_id) REFERENCES product(product_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pricing_recommendation (
    product_id          VARCHAR(10)    NOT NULL,
    category            VARCHAR(30)    NOT NULL,
    current_price       DECIMAL(10,2)  NOT NULL,
    recommended_price   DECIMAL(10,2)  NOT NULL,
    change_pct          DECIMAL(8,4)   NOT NULL,
    elasticity          DECIMAL(8,4)   NOT NULL,
    baseline_demand     DECIMAL(12,2)  NOT NULL,
    expected_demand     DECIMAL(12,2)  NOT NULL,
    available_stock     INT            NOT NULL,
    current_revenue     DECIMAL(14,2)  NOT NULL,
    expected_revenue    DECIMAL(14,2)  NOT NULL,
    revenue_change_pct  DECIMAL(8,4)   NOT NULL,
    unit_cost           DECIMAL(10,4)  NOT NULL,
    margin_pct          DECIMAL(8,4)   NOT NULL,
    expected_profit     DECIMAL(14,2)  NOT NULL,
    stock_limited       TINYINT(1)     NOT NULL,
    binding_constraint  VARCHAR(30)    NOT NULL,
    reason_codes        VARCHAR(100)   NOT NULL DEFAULT '',
    model_type          VARCHAR(30)    NOT NULL,
    forecast_week       VARCHAR(10)    NOT NULL,
    generated_at        DATETIME       NOT NULL,
    CONSTRAINT pk_pricing_recommendation PRIMARY KEY (product_id),
    CONSTRAINT fk_recommendation_product FOREIGN KEY (product_id) REFERENCES product(product_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS llm_explanation (
    explanation_id    INT            NOT NULL,
    entity_type       VARCHAR(10)    NOT NULL,
    entity_id         VARCHAR(20)    NOT NULL,
    explanation_text  VARCHAR(1000)  NOT NULL,
    source            VARCHAR(10)    NOT NULL,
    payload_json      TEXT           NOT NULL,
    payload_hash      CHAR(64)       NOT NULL,
    model_name        VARCHAR(60)    NOT NULL,
    guardrail_status  VARCHAR(10)    NOT NULL,
    rejection_reason  VARCHAR(255)   NOT NULL DEFAULT '',
    attempts          INT            NOT NULL,
    generated_at      DATETIME       NOT NULL,
    CONSTRAINT pk_llm_explanation PRIMARY KEY (explanation_id),
    CONSTRAINT uq_llm_explanation_entity UNIQUE (entity_type, entity_id)
) ENGINE=InnoDB;
