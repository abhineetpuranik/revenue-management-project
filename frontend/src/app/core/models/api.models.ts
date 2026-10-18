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
