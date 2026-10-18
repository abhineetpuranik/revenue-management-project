/**
 * Unit tests — ApiService
 *
 * Strategy: use Angular's HttpTestingController to intercept calls
 * and assert the correct URLs, params, and error handling.
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
  HealthResponse,
  Product,
  ForecastMetrics,
  ForecastResponse,
  SegmentsResponse,
  CustomersResponse,
  CustomerSegment,
} from '../models/api.models';

const BASE = 'http://localhost:5000';

describe('ApiService', () => {
  let service: ApiService;
  let controller: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        ApiService,
      ],
    });
    service = TestBed.inject(ApiService);
    controller = TestBed.inject(HttpTestingController);
  });

  // ── Health ──────────────────────────────────────────────────────────

  it('GET /api/health — returns status ok', () => {
    const mock: HealthResponse = { status: 'ok' };
    let result: HealthResponse | undefined;

    service.getHealth().subscribe((r) => (result = r));
    const req = controller.expectOne(`${BASE}/api/health`);
    expect(req.request.method).toBe('GET');
    req.flush(mock);

    expect(result).toEqual(mock);
    controller.verify();
  });

  // ── Products ────────────────────────────────────────────────────────

  it('GET /api/products — no filter', () => {
    const mock: Product[] = [
      { product_id: 'P001', category: 'Staples', base_price: 3.98 },
    ];
    let result: Product[] | undefined;

    service.getProducts().subscribe((r) => (result = r));
    const req = controller.expectOne(`${BASE}/api/products`);
    req.flush(mock);

    expect(result).toEqual(mock);
    controller.verify();
  });

  it('GET /api/products?category=Staples — passes category query param', () => {
    service.getProducts('Staples').subscribe();
    const req = controller.expectOne(
      (r) => r.url === `${BASE}/api/products` && r.params.get('category') === 'Staples'
    );
    req.flush([]);
    controller.verify();
  });

  // ── Forecast metrics ────────────────────────────────────────────────

  it('GET /api/forecast/metrics — returns full payload', () => {
    const mock: Partial<ForecastMetrics> = {
      selected_model: 'XGBoost',
      n_train: 7300,
      n_test: 400,
    };
    let result: ForecastMetrics | undefined;

    service.getForecastMetrics().subscribe((r) => (result = r));
    const req = controller.expectOne(`${BASE}/api/forecast/metrics`);
    req.flush(mock);

    expect((result as Partial<ForecastMetrics>)?.selected_model).toBe('XGBoost');
    controller.verify();
  });

  // ── Per-product forecast ────────────────────────────────────────────

  it('GET /api/forecast/:id — uses correct product ID in URL', () => {
    const mock: Partial<ForecastResponse> = {
      product_id: 'P001',
      series: [],
    };
    let result: ForecastResponse | undefined;

    service.getForecast('P001').subscribe((r) => (result = r));
    const req = controller.expectOne(`${BASE}/api/forecast/P001`);
    req.flush(mock);

    expect((result as Partial<ForecastResponse>)?.product_id).toBe('P001');
    controller.verify();
  });

  it('GET /api/forecast/:id — propagates 404 as DisplayError', () => {
    let error: { status: number; message: string } | undefined;

    service.getForecast('ZZZZ').subscribe({
      error: (e) => (error = e),
    });

    const req = controller.expectOne(`${BASE}/api/forecast/ZZZZ`);
    req.flush(
      { error: { status: 404, message: "Product 'ZZZZ' not found." } },
      { status: 404, statusText: 'Not Found' }
    );

    expect(error?.status).toBe(404);
    expect(error?.message).toContain('ZZZZ');
    controller.verify();
  });

  // ── Segments ────────────────────────────────────────────────────────

  it('GET /api/segments — returns overview', () => {
    const mock: Partial<SegmentsResponse> = {
      total_customers: 1000,
      n_clusters: 4,
      silhouette_score: 0.8573,
      segments: [],
    };
    let result: SegmentsResponse | undefined;

    service.getSegments().subscribe((r) => (result = r));
    const req = controller.expectOne(`${BASE}/api/segments`);
    req.flush(mock);

    expect((result as Partial<SegmentsResponse>)?.silhouette_score).toBe(0.8573);
    controller.verify();
  });

  it('GET /api/segments/customers — default page=1 page_size=50', () => {
    service.getCustomers().subscribe();
    const req = controller.expectOne(
      (r) =>
        r.url === `${BASE}/api/segments/customers` &&
        r.params.get('page') === '1' &&
        r.params.get('page_size') === '50'
    );
    req.flush({ customers: [], total: 0, page: 1, page_size: 50, pages: 0 });
    controller.verify();
  });

  it('GET /api/segments/customers — passes segment filter', () => {
    service.getCustomers('high_value', 2, 25).subscribe();
    const req = controller.expectOne(
      (r) =>
        r.url === `${BASE}/api/segments/customers` &&
        r.params.get('segment') === 'high_value' &&
        r.params.get('page') === '2' &&
        r.params.get('page_size') === '25'
    );
    req.flush({ customers: [], total: 0, page: 2, page_size: 25, pages: 1 } as CustomersResponse);
    controller.verify();
  });

  it('GET /api/customers/:id/segment — uses correct ID', () => {
    const mock: CustomerSegment = {
      customer_id: 'C0001',
      segment_label: 'regular',
      recency_days: 1,
      frequency: 861,
      monetary: 31198.8,
    };
    let result: CustomerSegment | undefined;

    service.getCustomerSegment('C0001').subscribe((r) => (result = r));
    const req = controller.expectOne(`${BASE}/api/customers/C0001/segment`);
    req.flush(mock);

    expect(result?.segment_label).toBe('regular');
    controller.verify();
  });

  // ── Network error ───────────────────────────────────────────────────

  it('network error — returns status 0 with helpful message', () => {
    let error: { status: number; message: string } | undefined;

    service.getHealth().subscribe({ error: (e) => (error = e) });
    const req = controller.expectOne(`${BASE}/api/health`);
    req.error(new ProgressEvent('error'), { status: 0 });

    expect(error?.status).toBe(0);
    expect(error?.message).toContain('Unable to connect');
    controller.verify();
  });
});
