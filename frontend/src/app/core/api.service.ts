/**
 * API service — typed HTTP client for all Phase 10a endpoints.
 * Components must never call HttpClient directly; use this service instead.
 */

import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import type {
  ApiError,
  CustomersResponse,
  ForecastMetrics,
  ForecastResponse,
  HealthResponse,
  Product,
  CustomerSegment,
  SegmentsResponse,
} from './models/api.models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  /* ── Health ─────────────────────────────────────────────────────────── */

  getHealth(): Observable<HealthResponse> {
    return this.http
      .get<HealthResponse>(`${this.baseUrl}/api/health`)
      .pipe(catchError(this.handleError));
  }

  /* ── Products ───────────────────────────────────────────────────────── */

  getProducts(category?: string): Observable<Product[]> {
    let params = new HttpParams();
    if (category) {
      params = params.set('category', category);
    }
    return this.http
      .get<Product[]>(`${this.baseUrl}/api/products`, { params })
      .pipe(catchError(this.handleError));
  }

  /* ── Forecast ───────────────────────────────────────────────────────── */

  getForecastMetrics(): Observable<ForecastMetrics> {
    return this.http
      .get<ForecastMetrics>(`${this.baseUrl}/api/forecast/metrics`)
      .pipe(catchError(this.handleError));
  }

  getForecast(productId: string): Observable<ForecastResponse> {
    return this.http
      .get<ForecastResponse>(`${this.baseUrl}/api/forecast/${productId}`)
      .pipe(catchError(this.handleError));
  }

  /* ── Segments ───────────────────────────────────────────────────────── */

  getSegments(): Observable<SegmentsResponse> {
    return this.http
      .get<SegmentsResponse>(`${this.baseUrl}/api/segments`)
      .pipe(catchError(this.handleError));
  }

  getCustomers(segment?: string, page = 1, pageSize = 50): Observable<CustomersResponse> {
    let params = new HttpParams().set('page', page.toString()).set('page_size', pageSize.toString());
    if (segment) {
      params = params.set('segment', segment);
    }
    return this.http
      .get<CustomersResponse>(`${this.baseUrl}/api/segments/customers`, { params })
      .pipe(catchError(this.handleError));
  }

  getCustomerSegment(customerId: string): Observable<CustomerSegment> {
    return this.http
      .get<CustomerSegment>(`${this.baseUrl}/api/customers/${customerId}/segment`)
      .pipe(catchError(this.handleError));
  }

  /* ── Error handling ─────────────────────────────────────────────────── */

  private handleError(error: HttpErrorResponse): Observable<never> {
    // Network error or server unreachable
    if (error.status === 0) {
      return throwError(() => ({
        status: 0,
        message: 'Unable to connect to the server. Check that the backend is running.',
      }));
    }

    // API returned an error in the standard format
    if (error.error && typeof error.error === 'object' && 'error' in error.error) {
      const apiError = error.error as ApiError;
      return throwError(() => ({
        status: apiError.error.status,
        message: apiError.error.message,
      }));
    }

    // Unexpected error shape
    return throwError(() => ({
      status: error.status,
      message: error.message || 'An unexpected error occurred.',
    }));
  }
}

/**
 * Error shape returned by handleError for display in components.
 */
export interface DisplayError {
  status: number;
  message: string;
}
