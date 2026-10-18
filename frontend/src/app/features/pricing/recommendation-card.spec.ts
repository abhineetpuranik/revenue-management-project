/**
 * Unit tests — RecommendationCardComponent
 */

import { describe, it, expect } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { RecommendationCardComponent } from './recommendation-card.component';
import type { PricingRecommendation } from '../../core/models/api.models';

function makeRec(overrides: Partial<PricingRecommendation> = {}): PricingRecommendation {
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

describe('RecommendationCardComponent', () => {
  function create() {
    const fixture = TestBed.createComponent(RecommendationCardComponent);
    return { fixture, comp: fixture.componentInstance };
  }

  it('renders current price and recommended price', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec());
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    expect(el.textContent).toContain('£3.28');
    expect(el.textContent).toContain('£3.77');
  });

  it('shows INCREASE tag when recommended > current', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec({ recommended_price: 3.77, current_price: 3.28 }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('INCREASE');
  });

  it('shows DECREASE tag when recommended < current', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec({ recommended_price: 2.5, current_price: 3.28 }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('DECREASE');
  });

  it('shows KEEP tag when recommended === current', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec({ recommended_price: 3.28, current_price: 3.28 }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('KEEP');
  });

  it('shows positive revenue change with teal class', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec({ revenue_change_abs: 103.42, revenue_change_pct: 0.0769 }));
    fixture.detectChanges();
    const change = fixture.debugElement.query(By.css('.revenue-change'));
    expect(change.classes['revenue-change--positive']).toBe(true);
    expect(change.nativeElement.textContent).toContain('↑');
    expect(change.nativeElement.textContent).toContain('+');
  });

  it('shows negative revenue change with coral class and down arrow', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec({ revenue_change_abs: -129.56, revenue_change_pct: -0.0487 }));
    fixture.detectChanges();
    const change = fixture.debugElement.query(By.css('.revenue-change'));
    expect(change.classes['revenue-change--negative']).toBe(true);
    expect(change.nativeElement.textContent).toContain('↓');
  });

  it('shows elasticity value and helper text', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec({ elasticity: -0.4676 }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('-0.4676');
    expect(fixture.nativeElement.textContent).toContain('More negative means demand reacts more strongly to price');
  });

  it('shows constraints applied chips', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec());
    fixture.detectChanges();
    const el: HTMLElement = fixture.nativeElement;
    expect(el.textContent).toContain('Min margin');
    expect(el.textContent).toContain('Max change');
  });

  it('shows reason codes when present', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec({ reason_codes: ['CURRENT_PRICE_BREAKS_MARGIN'] }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('CURRENT_PRICE_BREAKS_MARGIN');
  });

  it('shows no-recommendation state when recommendation_available is false', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec({
      recommendation_available: false,
      no_candidate_reason: 'NO_FEASIBLE_PRICE',
      binding_constraint: 'NO_FEASIBLE_PRICE',
      recommended_price: null,
      change_pct: null,
      expected_demand: null,
      expected_revenue: null,
      revenue_change_pct: null,
      revenue_change_abs: null,
      margin_pct: null,
      expected_profit: null,
    }));
    fixture.detectChanges();
    const noRec = fixture.debugElement.query(By.css('.no-recommendation'));
    expect(noRec).not.toBeNull();
    expect(noRec.nativeElement.textContent).toContain('No recommendation available');
    expect(noRec.nativeElement.textContent).toContain('NO_FEASIBLE_PRICE');
    // Still shows current price
    expect(noRec.nativeElement.textContent).toContain('£3.28');
  });

  it('shows binding constraint when present', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec({ binding_constraint: 'MARGIN' }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Binding');
    expect(fixture.nativeElement.textContent).toContain('MARGIN');
  });

  it('shows product ID in caption', () => {
    const { fixture } = create();
    fixture.componentRef.setInput('recommendation', makeRec({ product_id: 'P042' }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('P042');
  });
});
