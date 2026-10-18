/**
 * TypeScript interfaces mirroring /docs/api.md (Phase 10a endpoints).
 * All field names are snake_case to match the API exactly.
 */

/* ── Common ─────────────────────────────────────────────────────────────── */

export interface ApiError {
  error: {
    status: number;
    message: string;
  };
}

export interface HealthResponse {
  status: 'ok';
}

/* ── Products ───────────────────────────────────────────────────────────── */

export interface Product {
  product_id: string;
  category: string;
  base_price: number;
}

/* ── Forecast ───────────────────────────────────────────────────────────── */

export interface ForecastMetrics {
  models: {
    LinearRegression: ModelMetrics;
    XGBoost: ModelMetrics;
  };
  selected_model: 'LinearRegression' | 'XGBoost';
  selected_reason: string;
  n_train: number;
  n_test: number;
  train_start: string;  // YYYY-MM-DD
  train_end: string;
  test_start: string;
  test_end: string;
  trained_at: string;  // ISO timestamp string
}

export interface ModelMetrics {
  mae: number;
  mape: number;
  rmse: number;
}

export interface ForecastResponse {
  product_id: string;
  model_type: string;
  test_start: string;
  test_end: string;
  series: ForecastDataPoint[];
}

export interface ForecastDataPoint {
  week_start_date: string;  // YYYY-MM-DD
  iso_year: number;
  iso_week: number;
  row_type: 'history' | 'test';
  actual_units: number;
  predicted_units?: number;  // only present when row_type === 'test'
}

/* ── Segments ───────────────────────────────────────────────────────────── */

export type SegmentLabel = 'high_value' | 'regular' | 'occasional' | 'at_risk';

export interface SegmentsResponse {
  total_customers: number;
  n_clusters: number;
  silhouette_score: number;
  segments: SegmentSummary[];
}

export interface SegmentSummary {
  segment_label: SegmentLabel;
  customer_count: number;
  share_pct: number;
  revenue_share_pct: number;
  mean_recency_days: number;
  mean_frequency: number;
  mean_monetary: number;
  median_recency_days: number;
  median_frequency: number;
  median_monetary: number;
}

export interface CustomersResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  customers: CustomerSegment[];
}

export interface CustomerSegment {
  customer_id: string;
  segment_label: SegmentLabel;
  recency_days: number;
  frequency: number;
  monetary: number;
}

/* ── Pricing (Phase 10b) ─────────────────────────────────────────────────── */

/**
 * Binding constraint values returned by Phase 8.
 * MAX_CHANGE = price change cap hit; MARGIN = margin floor hit;
 * STOCK = stock constraint active; NO_FEASIBLE_PRICE = no valid candidate.
 */
export type BindingConstraint =
  | 'MAX_CHANGE'
  | 'MARGIN'
  | 'STOCK'
  | 'NO_FEASIBLE_PRICE'
  | string; // safety net for future values

/**
 * Full pricing recommendation for one product.
 * All monetary fields are plain floats (no currency symbol).
 * `recommendation_available: false` means no feasible price existed —
 * most numeric fields will still be present but `recommended_price` may be absent.
 */
export interface PricingRecommendation {
  product_id: string;
  category: string;
  recommendation_available: boolean;
  no_candidate_reason: string | null;
  current_price: number;
  current_revenue: number;
  unit_cost: number;
  available_stock: number;
  elasticity: number;
  baseline_demand: number;
  recommended_price: number | null;
  change_pct: number | null;
  expected_demand: number | null;
  expected_revenue: number | null;
  revenue_change_pct: number | null;
  revenue_change_abs: number | null;
  margin_pct: number | null;
  expected_profit: number | null;
  stock_limited: boolean;
  binding_constraint: BindingConstraint | null;
  reason_codes: string[];
  constraints_applied: {
    min_margin_pct: number;
    max_price_change_pct: number;
  };
  model_type: string;
  forecast_week: string;
  generated_at: string;
}

/** Paginated wrapper returned by GET /api/pricing/recommendations */
export interface PricingRecommendationsResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  recommendations: PricingRecommendation[];
}

/* ── Explanations (Phase 10b) ────────────────────────────────────────────── */

export type ExplanationSource = 'llm' | 'fallback' | 'mock' | null;
export type ExplanationEntityType = 'pricing' | 'segment' | null;

/**
 * Explanation response — shared shape for pricing and segment endpoints.
 * `explanation_available: false` when not yet generated, or after an internal error.
 * `source: null` and `generated_at: null` when unavailable.
 */
export interface ExplanationResponse {
  entity_type: ExplanationEntityType;
  entity_id: string;
  explanation_available: boolean;
  explanation: string | null;
  /** Present when unavailable_reason is set (unavailable or error cases) */
  unavailable_reason?: string;
  source: ExplanationSource;
  guardrail_status: string | null;
  model_name: string | null;
  attempts: number | null;
  payload: Record<string, string> | null;
  generated_at: string | null;
}
