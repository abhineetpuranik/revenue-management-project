/**
 * Unit tests — ApiService Phase 10b methods (pricing + explanations)
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { ApiService } from '../api.service';
import type {
  PricingRecommendation,
  PricingRecommendationsResponse,
  ExplanationResponse,
} from '../models/api.models';

const BASE = 'http://localhost:5000';

describe('ApiService — Pricing methods', () => {
  let service: ApiService;
  let controller: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiService],
    });
    service = TestBed.inject(ApiService);
    controller = TestBed.inject(HttpTestingController);
  });

  // ── getPricing ────────────────────────────────────────────────────────

  it('GET /api/pricing/:id — correct URL', () => {
    service.getPricing('P001').subscribe();
    const req = controller.expectOne(`${BASE}/api/pricing/P001`);
    expect(req.request.method).toBe('GET');
    req.flush({ product_id: 'P001', recommendation_available: true } as Partial<PricingRecommendation>);
    controller.verify();
  });

  it('GET /api/pricing/:id — 404 propagates as DisplayError', () => {
    let error: { status: number; message: string } | undefined;
    service.getPricing('ZZZZ').subscribe({ error: (e) => (error = e) });
    const req = controller.expectOne(`${BASE}/api/pricing/ZZZZ`);
    req.flush(
      { error: { status: 404, message: "Product 'ZZZZ' not found." } },
      { status: 404, statusText: 'Not Found' },
    );
    expect(error?.status).toBe(404);
    expect(error?.message).toContain('ZZZZ');
    controller.verify();
  });

  // ── getPricingRecommendations ─────────────────────────────────────────

  it('GET /api/pricing/recommendations — default page=1 page_size=50', () => {
    service.getPricingRecommendations().subscribe();
    const req = controller.expectOne(
      (r) =>
        r.url === `${BASE}/api/pricing/recommendations` &&
        r.params.get('page') === '1' &&
        r.params.get('page_size') === '50',
    );
    req.flush({
      total: 50,
      page: 1,
      page_size: 50,
      pages: 1,
      recommendations: [],
    } as PricingRecommendationsResponse);
    controller.verify();
  });

  it('GET /api/pricing/recommendations — passes category + page + page_size', () => {
    service.getPricingRecommendations('Electronics', 2, 25).subscribe();
    const req = controller.expectOne(
      (r) =>
        r.url === `${BASE}/api/pricing/recommendations` &&
        r.params.get('category') === 'Electronics' &&
        r.params.get('page') === '2' &&
        r.params.get('page_size') === '25',
    );
    req.flush({
      total: 8,
      page: 2,
      page_size: 25,
      pages: 1,
      recommendations: [],
    } as PricingRecommendationsResponse);
    controller.verify();
  });

  // ── getPricingExplanation ─────────────────────────────────────────────

  it('GET /api/pricing/:id/explanation — correct URL', () => {
    service.getPricingExplanation('P027').subscribe();
    const req = controller.expectOne(`${BASE}/api/pricing/P027/explanation`);
    expect(req.request.method).toBe('GET');
    req.flush({ explanation_available: true, explanation: 'test' } as Partial<ExplanationResponse>);
    controller.verify();
  });

  // ── getSegmentExplanation ────────────────────────────────────────────

  it('GET /api/segments/:label/explanation — correct URL', () => {
    service.getSegmentExplanation('high_value').subscribe();
    const req = controller.expectOne(`${BASE}/api/segments/high_value/explanation`);
    expect(req.request.method).toBe('GET');
    req.flush({
      entity_type: 'segment',
      entity_id: 'high_value',
      explanation_available: true,
      explanation: 'High-value customers...',
    } as Partial<ExplanationResponse>);
    controller.verify();
  });
});
