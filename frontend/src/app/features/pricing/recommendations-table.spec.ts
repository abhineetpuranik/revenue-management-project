/**
 * Unit tests — RecommendationsTableComponent
 */

import { describe, it, expect } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { RecommendationsTableComponent } from './recommendations-table.component';
import type {
  PricingRecommendationsResponse,
  PricingRecommendation,
} from '../../core/models/api.models';

function makeRow(overrides: Partial<PricingRecommendation> = {}): PricingRecommendation {
  return {
    product_id: 'P001',
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
    ...overrides,
  };
}

function makeResponse(
  rows: PricingRecommendation[],
  page = 1,
  pages = 1,
  total = rows.length,
): PricingRecommendationsResponse {
  return { total, page, page_size: 50, pages, recommendations: rows };
}

describe('RecommendationsTableComponent', () => {
  function create() {
    const fixture = TestBed.createComponent(RecommendationsTableComponent);
    return { fixture, comp: fixture.componentInstance };
  }

  it('renders rows with product, category, prices', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('data', makeResponse([makeRow({ product_id: 'P001', category: 'Staples' })]));
    fixture.detectChanges();
    const cells = fixture.debugElement.queryAll(By.css('td'));
    expect(cells.length).toBeGreaterThan(0);
    expect(fixture.nativeElement.textContent).toContain('P001');
    expect(fixture.nativeElement.textContent).toContain('Staples');
    expect(fixture.nativeElement.textContent).toContain('£3.28');
    expect(fixture.nativeElement.textContent).toContain('£3.77');
  });

  it('renders availability badge — available', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('data', makeResponse([makeRow({ recommendation_available: true })]));
    fixture.detectChanges();
    const badge = fixture.debugElement.query(By.css('.avail-badge--available'));
    expect(badge).not.toBeNull();
  });

  it('renders availability badge — none', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('data', makeResponse([
      makeRow({ recommendation_available: false, recommended_price: null, change_pct: null }),
    ]));
    fixture.detectChanges();
    const badge = fixture.debugElement.query(By.css('.avail-badge--none'));
    expect(badge).not.toBeNull();
  });

  it('row click emits selectProduct with product_id', () => {
    const { fixture, comp } = create();
    fixture.componentRef.setInput('data', makeResponse([makeRow({ product_id: 'P042' })]));
    fixture.detectChanges();

    let selectedId: string | undefined;
    comp.selectProduct.subscribe((id) => (selectedId = id));

    const row = fixture.debugElement.query(By.css('.rec-row'));
    (row.nativeElement as HTMLElement).click();
    expect(selectedId).toBe('P042');
  });

  it('Enter key on row emits selectProduct', () => {
    const { fixture, comp } = create();
    fixture.componentRef.setInput('data', makeResponse([makeRow({ product_id: 'P010' })]));
    fixture.detectChanges();

    let selectedId: string | undefined;
    comp.selectProduct.subscribe((id) => (selectedId = id));

    const row = fixture.debugElement.query(By.css('.rec-row'));
    row.triggerEventHandler('keydown.enter', null);
    expect(selectedId).toBe('P010');
  });

  it('Prev button disabled on page 1', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('data', makeResponse([makeRow()], 1, 3, 100));
    fixture.detectChanges();
    const buttons = fixture.debugElement.queryAll(By.css('.pagination-btn'));
    const prev = buttons[0];
    expect(prev.properties['disabled']).toBe(true);
  });

  it('Next button disabled on last page', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('data', makeResponse([makeRow()], 3, 3, 100));
    fixture.detectChanges();
    const buttons = fixture.debugElement.queryAll(By.css('.pagination-btn'));
    const next = buttons[1];
    expect(next.properties['disabled']).toBe(true);
  });

  it('pagination button click emits goToPage', () => {
    const { fixture, comp } = create();
    fixture.componentRef.setInput('data', makeResponse([makeRow()], 2, 3, 100));
    fixture.detectChanges();

    let pageNum: number | undefined;
    comp.goToPage.subscribe((p) => (pageNum = p));

    const buttons = fixture.debugElement.queryAll(By.css('.pagination-btn'));
    (buttons[0].nativeElement as HTMLButtonElement).click();
    expect(pageNum).toBe(1);
  });

  it('shows loading state', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('loading', true);
    fixture.componentRef.setInput('data', null);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Loading recommendations');
  });

  it('shows error state with retry', () => {
    const { fixture, comp } = create();
    fixture.componentRef.setInput('error', 'Failed to load.');
    fixture.componentRef.setInput('data', null);
    fixture.detectChanges();

    let retried = false;
    comp.retry.subscribe(() => (retried = true));

    const btn = fixture.debugElement.query(By.css('button'));
    expect(btn).not.toBeNull();
    (btn.nativeElement as HTMLButtonElement).click();
    expect(retried).toBe(true);
  });

  it('shows empty state when recommendations array is empty', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('data', makeResponse([]));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No recommendations found');
  });

  it('highlights selected product row', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('data', makeResponse([makeRow({ product_id: 'P001' }), makeRow({ product_id: 'P002' })]));
    fixture.componentRef.setInput('selectedProductId', 'P002');
    fixture.detectChanges();
    const rows = fixture.debugElement.queryAll(By.css('.rec-row'));
    expect(rows[1].classes['rec-row--selected']).toBe(true);
    // Angular only adds present classes to .classes — absent class is undefined
    expect(rows[0].classes['rec-row--selected']).not.toBe(true);
  });
});
