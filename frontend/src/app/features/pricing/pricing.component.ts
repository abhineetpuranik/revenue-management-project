/**
 * Pricing view — Phase 11b
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────────────┐
 *   │ Page header  [ 03 / PRICING ]                           │
 *   ├──────────┬────────────────────────────────────────────────┤
 *   │ Sidebar  │ Recommendation card (detail)                   │
 *   │  chips   ├────────────────────────────────────────────────┤
 *   │  product │ Explanation panel                              │
 *   │  select  ├────────────────────────────────────────────────┤
 *   │          │ Recommendations table (paginated, filtered)   │
 *   └──────────┴────────────────────────────────────────────────┘
 *
 * Stale-response guard: each product change increments a request token.
 * Only the subscriber holding the latest token may write to signals.
 * In-flight HTTP requests are cancelled via takeUntilDestroyed + switchMap.
 *
 * Explanation timeout: a named constant slightly above the backend LLM timeout.
 * On timeout, the panel shows the error state with Retry.
 */

import {
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { timer, of, throwError } from 'rxjs';
import { delay, filter, map, switchMap, catchError, take } from 'rxjs/operators';

import { ApiService } from '../../core/api.service';
import type {
  ExplanationResponse,
  PricingRecommendation,
  PricingRecommendationsResponse,
  Product,
} from '../../core/models/api.models';
import { CardComponent } from '../../shared/components/card.component';
import { CategoryChipsComponent } from '../../shared/components/category-chips.component';
import { ExplanationPanelComponent, ExplanationState } from '../../shared/components/explanation-panel.component';
import type { ExplanationSource } from '../../core/models/api.models';
import { LoadingStateComponent } from '../../shared/components/loading-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header.component';
import { ProductSelectComponent } from '../../shared/components/product-select.component';
import { RecommendationCardComponent } from './recommendation-card.component';
import { RecommendationsTableComponent } from './recommendations-table.component';

const CATEGORIES = ['All', 'Staples', 'Personal Care', 'Electronics', 'Clothing', 'Impulse'];

/**
 * Frontend timeout for the explanation request.
 * The backend's LLM timeout is ~30s; we add a 5s buffer so the UI never
 * spins forever if the server hangs without responding.
 */
const EXPLANATION_TIMEOUT_MS = 35_000;

@Component({
  selector: 'app-pricing',
  standalone: true,
  imports: [
    PageHeaderComponent,
    CardComponent,
    CategoryChipsComponent,
    ProductSelectComponent,
    RecommendationCardComponent,
    ExplanationPanelComponent,
    RecommendationsTableComponent,
    LoadingStateComponent,
    ErrorStateComponent,
  ],
  templateUrl: './pricing.component.html',
  styleUrl: './pricing.component.scss',
})
export class PricingComponent implements OnInit {
  private api = inject(ApiService);
  private destroyRef = inject(DestroyRef);

  // ── Product catalog ───────────────────────────────────────────────────
  products = signal<Product[]>([]);
  productsLoading = signal(true);
  productsError = signal<string | null>(null);

  selectedCategory = signal<string>('All');
  selectedProductId = signal<string>('');

  readonly categories = CATEGORIES;

  filteredProducts = computed(() => {
    let list = this.products();
    const cat = this.selectedCategory();
    if (cat !== 'All') list = list.filter((p) => p.category === cat);
    return list;
  });

  // ── Recommendation detail ─────────────────────────────────────────────
  recommendation = signal<PricingRecommendation | null>(null);
  recLoading = signal(false);
  recError = signal<string | null>(null);

  // ── Explanation ───────────────────────────────────────────────────────
  explanationState = signal<ExplanationState>('loading');
  explanationText = signal<string | null>(null);
  explanationReason = signal<string | null>(null);
  explanationSource = signal<string | null>(null);

  // Cast for the panel's typed input
  explanationSourceTyped = computed<ExplanationSource>(() => {
    const s = this.explanationSource();
    if (s === 'llm' || s === 'fallback' || s === 'mock') return s;
    return null;
  });
  explanationGeneratedAt = signal<string | null>(null);

  // ── Stale-response guard (separate tokens for rec and explanation) ────
  private recToken = 0;
  private expToken = 0;

  // ── Recommendations table ─────────────────────────────────────────────
  tableData = signal<PricingRecommendationsResponse | null>(null);
  tableLoading = signal(false);
  tableError = signal<string | null>(null);
  tablePage = signal(1);
  readonly tablePageSize = 50;

  ngOnInit(): void {
    this.loadProducts();
    this.loadTable();
  }

  private loadProducts(): void {
    this.productsLoading.set(true);
    this.productsError.set(null);
    this.api
      .getProducts()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (products) => {
          this.products.set(products);
          this.productsLoading.set(false);
          if (products.length > 0) {
            this.selectProduct(products[0].product_id);
          }
        },
        error: (err) => {
          this.productsError.set(err.message ?? 'Failed to load products.');
          this.productsLoading.set(false);
        },
      });
  }

  selectCategory(cat: string): void {
    this.selectedCategory.set(cat);
    // If the currently selected product is not in this category, select the first match
    const filtered = this.filteredProducts();
    if (
      !filtered.find((p) => p.product_id === this.selectedProductId()) &&
      filtered.length > 0
    ) {
      this.selectProduct(filtered[0].product_id);
    }
    // Reset table to page 1 and reload with category filter
    this.tablePage.set(1);
    this.loadTable();
  }

  selectProduct(productId: string): void {
    this.selectedProductId.set(productId);
    this.loadRecommendation(productId);
    this.loadExplanation(productId);
  }

  retryProducts(): void {
    this.loadProducts();
  }

  retryRecommendation(): void {
    const id = this.selectedProductId();
    if (id) this.loadRecommendation(id);
  }

  retryExplanation(): void {
    const id = this.selectedProductId();
    if (id) this.loadExplanation(id);
  }

  retryTable(): void {
    this.loadTable();
  }

  goToTablePage(page: number): void {
    this.tablePage.set(page);
    this.loadTable();
  }

  selectProductFromTable(productId: string): void {
    // If the product is in a different category, switch the category too
    const product = this.products().find((p) => p.product_id === productId);
    if (product && this.selectedCategory() !== 'All' && product.category !== this.selectedCategory()) {
      this.selectedCategory.set('All');
    }
    this.selectProduct(productId);
    // Scroll the detail section into view
    setTimeout(() => {
      const el = document.getElementById('pricing-detail');
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 100);
  }

  // ── Recommendation loading (numbers first, no waiting on explanation) ───

  private loadRecommendation(productId: string): void {
    const token = ++this.recToken;
    this.recLoading.set(true);
    this.recError.set(null);
    this.recommendation.set(null);

    this.api
      .getPricing(productId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (rec) => {
          if (token !== this.recToken) return; // stale
          this.recommendation.set(rec);
          this.recLoading.set(false);
        },
        error: (err) => {
          if (token !== this.recToken) return; // stale
          this.recError.set(err.message ?? 'Failed to load pricing recommendation.');
          this.recLoading.set(false);
        },
      });
  }

  // ── Explanation loading (fetched after recommendation, with timeout) ──────

  private loadExplanation(productId: string): void {
    const token = ++this.expToken;
    this.explanationState.set('loading');
    this.explanationText.set(null);
    this.explanationReason.set(null);
    this.explanationSource.set(null);
    this.explanationGeneratedAt.set(null);

    // Race the HTTP call against a timeout timer
    this.api
      .getPricingExplanation(productId)
      .pipe(
        takeUntilDestroyed(this.destroyRef),
        switchMap((resp: ExplanationResponse) => {
          // If the response arrives within the timeout, check it's not stale
          if (token !== this.expToken) {
            // Stale: discard silently
            return of<ExplanationResponse | null>(null);
          }
          return of<ExplanationResponse | null>(resp);
        }),
        // Apply timeout via a separate race
        // We use a timer that emits a sentinel after EXPLANATION_TIMEOUT_MS
        catchError((err) => {
          if (token !== this.expToken) return of<ExplanationResponse | null>(null);
          // Re-throw to the error handler below
          return throwError(() => err);
        }),
      )
      .subscribe({
        next: (resp) => {
          if (resp === null) return; // stale or timed-out sentinel
          if (token !== this.expToken) return; // stale

          if (resp.explanation_available && resp.explanation) {
            this.explanationState.set('available');
            this.explanationText.set(resp.explanation);
            this.explanationSource.set(resp.source);
            this.explanationGeneratedAt.set(resp.generated_at);
          } else {
            this.explanationState.set('unavailable');
            this.explanationReason.set(
              resp.unavailable_reason ??
                'No explanation has been generated yet.',
            );
          }
        },
        error: (err) => {
          if (token !== this.expToken) return; // stale
          this.explanationState.set('error');
          this.explanationReason.set(err.message ?? 'Failed to load explanation.');
        },
      });

    // Separate timeout race: if the HTTP call doesn't complete within
    // EXPLANATION_TIMEOUT_MS, show the error state.
    timer(EXPLANATION_TIMEOUT_MS)
      .pipe(takeUntilDestroyed(this.destroyRef), take(1))
      .subscribe(() => {
        if (token !== this.expToken) return; // already superseded
        if (this.explanationState() === 'loading') {
          this.explanationState.set('error');
          this.explanationReason.set(
            'The explanation request timed out. The LLM may be slow or unavailable.',
          );
        }
      });
  }

  // ── Table loading ────────────────────────────────────────────────────

  private loadTable(): void {
    this.tableLoading.set(true);
    this.tableError.set(null);
    const category = this.selectedCategory() !== 'All' ? this.selectedCategory() : undefined;
    this.api
      .getPricingRecommendations(category, this.tablePage(), this.tablePageSize)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (resp) => {
          this.tableData.set(resp);
          this.tableLoading.set(false);
        },
        error: (err) => {
          this.tableError.set(err.message ?? 'Failed to load recommendations.');
          this.tableLoading.set(false);
        },
      });
  }
}
