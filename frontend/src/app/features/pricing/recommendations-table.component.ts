/**
 * Recommendations table component — paginated overview of all product recommendations.
 *
 * Displays product, category, current/recommended price, change %, revenue
 * change, and availability indicator. Paginated with the same controls and
 * page size (50) as the Segments customer table. Filtered by the selected
 * category. Clicking a row (or pressing Enter) selects that product in the
 * parent detail section.
 *
 * Loading, error, and empty states are independent of the detail card.
 */

import { Component, computed, input, output } from '@angular/core';

import type { PricingRecommendationsResponse, PricingRecommendation } from '../../core/models/api.models';
import { CardComponent } from '../../shared/components/card.component';
import { EmptyStateComponent } from '../../shared/components/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state.component';
import { LoadingStateComponent } from '../../shared/components/loading-state.component';

const CURRENCY_SYMBOL = '₹';

@Component({
  selector: 'app-recommendations-table',
  standalone: true,
  imports: [CardComponent, LoadingStateComponent, ErrorStateComponent, EmptyStateComponent],
  template: `
    <app-card caption="ALL RECOMMENDATIONS">
      @if (loading()) {
        <app-loading-state message="Loading recommendations…" />
      } @else if (error()) {
        <app-error-state [message]="error()!" (retry)="retry.emit()" />
      } @else if (data() && data()!.recommendations.length === 0) {
        <app-empty-state message="No recommendations found for this filter." />
      } @else if (data(); as resp) {
        <div class="table-scroll">
          <table class="data-table" aria-label="Pricing recommendations">
            <thead>
              <tr>
                <th class="mono">Product</th>
                <th class="mono">Category</th>
                <th class="mono cell--number">Current</th>
                <th class="mono cell--number">Recommended</th>
                <th class="mono cell--number">Change</th>
                <th class="mono cell--number">Revenue Δ</th>
                <th class="mono">Status</th>
              </tr>
            </thead>
            <tbody>
              @for (row of resp.recommendations; track row.product_id) {
                <tr
                  class="rec-row"
                  [class.rec-row--selected]="selectedProductId() === row.product_id"
                  (click)="selectProduct.emit(row.product_id)"
                  (keydown.enter)="selectProduct.emit(row.product_id)"
                  [tabindex]="0"
                  role="button"
                  [attr.aria-label]="'Select product ' + row.product_id"
                >
                  <td class="mono rec-row__id">{{ row.product_id }}</td>
                  <td class="mono">{{ row.category }}</td>
                  <td class="mono cell--number">{{ CURRENCY_SYMBOL }}{{ formatNum(row.current_price) }}</td>
                  <td class="mono cell--number">
                    @if (row.recommendation_available && row.recommended_price !== null) {
                      {{ CURRENCY_SYMBOL }}{{ formatNum(row.recommended_price) }}
                    } @else {
                      —
                    }
                  </td>
                  <td class="mono cell--number">
                    @if (row.recommendation_available && row.change_pct !== null) {
                      {{ formatPct(row.change_pct) }}
                    } @else {
                      —
                    }
                  </td>
                  <td class="mono cell--number">
                    @if (row.recommendation_available && row.revenue_change_pct !== null) {
                      <span [class.cell--positive]="row.revenue_change_pct >= 0" [class.cell--negative]="row.revenue_change_pct < 0">
                        {{ row.revenue_change_pct >= 0 ? '+' : '' }}{{ formatPct(row.revenue_change_pct) }}
                      </span>
                    } @else {
                      —
                    }
                  </td>
                  <td>
                    @if (row.recommendation_available) {
                      <span class="avail-badge avail-badge--available mono">✓ Available</span>
                    } @else {
                      <span class="avail-badge avail-badge--none mono">None</span>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>

        <div class="pagination">
          <span class="pagination-info mono">
            Page {{ resp.page }} of {{ resp.pages }}
            ({{ resp.total.toLocaleString() }} total)
          </span>
          <button
            type="button"
            class="pagination-btn mono"
            [disabled]="resp.page === 1"
            (click)="goToPage.emit(resp.page - 1)"
          >
            ← Prev
          </button>
          <button
            type="button"
            class="pagination-btn mono"
            [disabled]="resp.page >= resp.pages"
            (click)="goToPage.emit(resp.page + 1)"
          >
            Next →
          </button>
        </div>
      }
    </app-card>
  `,
  styleUrl: './recommendations-table.component.scss',
})
export class RecommendationsTableComponent {
  data = input<PricingRecommendationsResponse | null>(null);
  loading = input<boolean>(false);
  error = input<string | null>(null);
  selectedProductId = input<string>('');

  selectProduct = output<string>();
  goToPage = output<number>();
  retry = output<void>();

  protected readonly CURRENCY_SYMBOL = CURRENCY_SYMBOL;

  formatNum(n: number | null | undefined, decimals = 2): string {
    if (n == null) return '—';
    return n.toFixed(decimals);
  }

  formatPct(n: number | null | undefined): string {
    if (n == null) return '—';
    return (n * 100).toFixed(1) + '%';
  }
}
