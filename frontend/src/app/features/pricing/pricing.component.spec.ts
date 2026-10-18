/**
 * Unit tests — PricingComponent
 *
 * Covers:
 *  - Stale-response guard: only the latest product's data is rendered
 *  - Explanation timeout path
 *
 * Uses Vitest fake timers instead of fakeAsync (which requires zone-testing).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import { PricingComponent } from './pricing.component';
import type { PricingRecommendation, PricingRecommendationsResponse } from '../../core/models/api.models';

const BASE = 'http://localhost:5000';

function makeRec(id: string): PricingRecommendation {
  return {
    product_id: id,
    category: 'Staples',
    recommendation_available: true,
    no_candidate_reason: null,
    current_price: 3.28,
    current_revenue: 1344.12,
    unit_cost: 2.786,
    available_stock: 17750,
    elasticity: -0.4676,
    baseline_demand: 409.79,
    recommended_price: 3.77,
    change_pct: 0.1494,
    expected_demand: 383.96,
    expected_revenue: 1447.54,
    revenue_change_pct: 0.0769,
    revenue_change_abs: 103.42,
    margin_pct: 0.261,
    expected_profit: 377.82,
    stock_limited: false,
    binding_constraint: 'MAX_CHANGE',
    reason_codes: [],
    constraints_applied: { min_margin_pct: 0.1, max_price_change_pct: 0.15 },
    model_type: 'XGBoost',
    forecast_week: '2025-W01',
    generated_at: '2026-10-14 00:03:48',
  };
}

function makeTableResp(): PricingRecommendationsResponse {
  return { total: 0, page: 1, page_size: 50, pages: 0, recommendations: [] };
}

describe('PricingComponent', () => {
  let controller: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [PricingComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    controller = TestBed.inject(HttpTestingController);
  });

  // ── Stale-response guard ───────────────────────────────────────────────

  it('stale guard — selecting a second product before first responds only shows second product', () => {
    vi.useFakeTimers();
    const fixture = TestBed.createComponent(PricingComponent);
    fixture.detectChanges();

    // Flush the initial product list and table
    controller
      .expectOne((r) => r.url.includes('/api/products'))
      .flush([
        { product_id: 'P001', category: 'Staples', base_price: 3.28 },
        { product_id: 'P002', category: 'Staples', base_price: 1.01 },
      ]);
    controller
      .expectOne((r) => r.url.includes('/api/pricing/recommendations'))
      .flush(makeTableResp());

    // After loading products, P001 is auto-selected — rec + explanation requests fired
    const recReq1 = controller.expectOne((r) => r.url === `${BASE}/api/pricing/P001`);
    const expReq1 = controller.expectOne((r) => r.url === `${BASE}/api/pricing/P001/explanation`);

    // User quickly selects P002 before P001 response arrives
    fixture.componentInstance.selectProduct('P002');
    fixture.detectChanges();

    // P002 rec + explanation requests fired
    const recReq2 = controller.expectOne((r) => r.url === `${BASE}/api/pricing/P002`);
    controller
      .expectOne((r) => r.url === `${BASE}/api/pricing/P002/explanation`)
      .flush({
        explanation_available: false,
        explanation: null,
        entity_id: 'P002',
        entity_type: 'pricing',
        source: null,
        guardrail_status: null,
        model_name: null,
        attempts: null,
        payload: null,
        generated_at: null,
        unavailable_reason: 'Not generated',
      });

    // Now resolve P001 AFTER P002 was selected — it is stale
    recReq1.flush(makeRec('P001'));
    expReq1.flush({
        explanation_available: true,
        explanation: 'P001 explanation',
        entity_id: 'P001',
        entity_type: 'pricing',
        source: 'llm',
        guardrail_status: 'passed',
        model_name: 'gemini',
        attempts: 1,
        payload: null,
        generated_at: '2026-10-15',
      });

    // Resolve P002
    recReq2.flush(makeRec('P002'));
    fixture.detectChanges();

    // Should show P002's recommendation, not P001's
    expect(fixture.componentInstance.recommendation()?.product_id).toBe('P002');
    // Explanation from P001 (stale) must not have been written to the signal
    expect(fixture.componentInstance.explanationText()).not.toBe('P001 explanation');

    vi.useRealTimers();
    controller.verify();
  });

  // ── Explanation timeout ────────────────────────────────────────────────

  it('explanation timeout — shows error state after 35s', () => {
    vi.useFakeTimers();
    const fixture = TestBed.createComponent(PricingComponent);
    fixture.detectChanges();

    controller
      .expectOne((r) => r.url.includes('/api/products'))
      .flush([{ product_id: 'P001', category: 'Staples', base_price: 3.28 }]);
    controller
      .expectOne((r) => r.url.includes('/api/pricing/recommendations'))
      .flush(makeTableResp());

    // Rec fires and resolves
    controller.expectOne((r) => r.url === `${BASE}/api/pricing/P001`).flush(makeRec('P001'));
    // Keep explanation request pending (never flush it)
    const expReq = controller.expectOne(
      (r) => r.url === `${BASE}/api/pricing/P001/explanation`,
    );
    fixture.detectChanges();

    // Explanation state should be 'loading'
    expect(fixture.componentInstance.explanationState()).toBe('loading');

    // Advance time past EXPLANATION_TIMEOUT_MS (35 000ms)
    vi.advanceTimersByTime(36_000);
    fixture.detectChanges();

    // Explanation state should now be 'error'
    expect(fixture.componentInstance.explanationState()).toBe('error');
    expect(fixture.componentInstance.explanationReason()).toContain('timed out');

    // Clean up the pending request
    expReq.flush({
      explanation_available: false,
      explanation: null,
      entity_id: 'P001',
      entity_type: 'pricing',
      source: null,
      guardrail_status: null,
      model_name: null,
      attempts: null,
      payload: null,
      generated_at: null,
    });

    vi.useRealTimers();
    controller.verify();
  });
});
