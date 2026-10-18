/**
 * Recommendation card component — displays a single product's pricing recommendation.
 *
 * Shows current vs. recommended price with a direction tag, expected revenue
 * comparison, elasticity, applied constraints, and a bar chart.
 *
 * When `recommendation_available` is false, shows a non-error state with the
 * reason and whatever current-price info the response contains.
 */

import { Component, computed, input } from '@angular/core';
import { ChartConfiguration, ChartDataset } from 'chart.js';

import type { PricingRecommendation } from '../../core/models/api.models';
import { CardComponent } from '../../shared/components/card.component';
import { ChartWrapperComponent } from '../../shared/components/chart-wrapper.component';

/** Currency symbol — taken from api.md glossary (monetary = "Total spend (£)"). */
const CURRENCY_SYMBOL = '£';

@Component({
  selector: 'app-recommendation-card',
  standalone: true,
  imports: [CardComponent, ChartWrapperComponent],
  template: `
    <app-card [caption]="caption()">
      @if (recommendation(); as rec) {
        @if (rec.recommendation_available) {
          <!-- ── Full recommendation ─────────────────────────────────────── -->
          <div class="rec-card">
            <!-- Price comparison -->
            <div class="price-comparison">
              <div class="price-block price-block--current">
                <div class="price-block__label text-micro mono uppercase">Current Price</div>
                <div class="price-block__value mono">{{ CURRENCY_SYMBOL }}{{ formatNum(rec.current_price) }}</div>
              </div>

              <div class="price-arrow" [class.price-arrow--up]="isIncrease()" [class.price-arrow--down]="isDecrease()" [class.price-arrow--keep]="isKeep()">
                <span class="price-arrow__symbol" aria-hidden="true">
                  {{ isIncrease() ? '↑' : isDecrease() ? '↓' : '→' }}
                </span>
                <span class="price-arrow__tag mono">
                  {{ isIncrease() ? 'INCREASE' : isDecrease() ? 'DECREASE' : 'KEEP' }}
                </span>
              </div>

              <div class="price-block price-block--recommended">
                <div class="price-block__label text-micro mono uppercase">Recommended</div>
                <div class="price-block__value mono">{{ CURRENCY_SYMBOL }}{{ formatNum(rec.recommended_price) }}</div>
              </div>
            </div>

            <!-- Change percent -->
            @if (rec.change_pct !== null) {
              <div class="change-pct mono">
                {{ formatPct(rec.change_pct) }} change
              </div>
            }

            <!-- Revenue comparison -->
            <div class="revenue-grid">
              <div class="revenue-tile revenue-tile--current">
                <div class="revenue-tile__label text-micro mono uppercase">Revenue at Current</div>
                <div class="revenue-tile__value mono">{{ CURRENCY_SYMBOL }}{{ formatNum(rec.current_revenue, 0) }}</div>
              </div>
              <div class="revenue-tile revenue-tile--expected">
                <div class="revenue-tile__label text-micro mono uppercase">Revenue at Recommended</div>
                <div class="revenue-tile__value mono">{{ CURRENCY_SYMBOL }}{{ formatNum(rec.expected_revenue, 0) }}</div>
              </div>
              <div class="revenue-change" [class.revenue-change--positive]="isRevenuePositive()" [class.revenue-change--negative]="!isRevenuePositive()">
                <span class="revenue-change__arrow" aria-hidden="true">
                  {{ isRevenuePositive() ? '↑' : '↓' }}
                </span>
                <span class="revenue-change__abs mono">{{ isRevenuePositive() ? '+' : '' }}{{ CURRENCY_SYMBOL }}{{ formatNum(rec.revenue_change_abs, 0) }}</span>
                <span class="revenue-change__pct mono">({{ formatPct(rec.revenue_change_pct) }})</span>
              </div>
            </div>

            <!-- Bar chart: current vs expected revenue -->
            <div class="chart-area">
              <app-chart-wrapper [config]="chartConfig()" />
            </div>

            <!-- Elasticity -->
            @if (rec.elasticity !== null) {
              <div class="elasticity-row">
                <div class="elasticity-tile">
                  <div class="elasticity-tile__label text-micro mono uppercase">Elasticity</div>
                  <div class="elasticity-tile__value mono">{{ formatNum(rec.elasticity, 4) }}</div>
                </div>
                <p class="elasticity-helper mono">
                  More negative means demand reacts more strongly to price.
                </p>
              </div>
            }

            <!-- Constraints applied -->
            <div class="constraints-section">
              <div class="constraints-section__label text-micro mono uppercase">Constraints Applied</div>
              <div class="constraints-chips">
                <span class="constraint-chip mono">
                  Min margin: {{ formatPct(rec.constraints_applied.min_margin_pct) }}
                </span>
                <span class="constraint-chip mono">
                  Max change: ±{{ formatPct(rec.constraints_applied.max_price_change_pct) }}
                </span>
                @if (rec.stock_limited) {
                  <span class="constraint-chip constraint-chip--active mono">
                    Stock limited: {{ rec.available_stock.toLocaleString() }} units
                  </span>
                }
              </div>
              @if (rec.binding_constraint) {
                <div class="binding-constraint mono">
                  Binding: <strong>{{ rec.binding_constraint }}</strong>
                </div>
              }
              @if (rec.reason_codes.length > 0) {
                <div class="reason-codes">
                  @for (code of rec.reason_codes; track code) {
                    <span class="reason-code mono">{{ code }}</span>
                  }
                </div>
              }
            </div>

            <!-- Extra details -->
            <div class="details-grid">
              <div class="detail-item">
                <span class="detail-item__label text-micro mono uppercase">Unit Cost</span>
                <span class="detail-item__value mono">{{ CURRENCY_SYMBOL }}{{ formatNum(rec.unit_cost) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-item__label text-micro mono uppercase">Expected Demand</span>
                <span class="detail-item__value mono">{{ formatNum(rec.expected_demand, 0) }} units</span>
              </div>
              <div class="detail-item">
                <span class="detail-item__label text-micro mono uppercase">Margin %</span>
                <span class="detail-item__value mono">{{ formatPct(rec.margin_pct) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-item__label text-micro mono uppercase">Expected Profit</span>
                <span class="detail-item__value mono">{{ CURRENCY_SYMBOL }}{{ formatNum(rec.expected_profit, 0) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-item__label text-micro mono uppercase">Baseline Demand</span>
                <span class="detail-item__value mono">{{ formatNum(rec.baseline_demand, 0) }} units</span>
              </div>
              <div class="detail-item">
                <span class="detail-item__label text-micro mono uppercase">Available Stock</span>
                <span class="detail-item__value mono">{{ rec.available_stock.toLocaleString() }} units</span>
              </div>
            </div>

            <div class="meta-row mono">
              <span>Model: {{ rec.model_type }}</span>
              <span>Week: {{ rec.forecast_week }}</span>
              <span>Generated: {{ rec.generated_at }}</span>
            </div>
          </div>
        } @else {
          <!-- ── No recommendation available ────────────────────────────── -->
          <div class="no-recommendation">
            <p class="no-recommendation__title mono">No recommendation available</p>
            @if (rec.no_candidate_reason) {
              <p class="no-recommendation__reason mono">{{ rec.no_candidate_reason }}</p>
            }
            @if (rec.binding_constraint) {
              <p class="no-recommendation__constraint mono">Binding constraint: {{ rec.binding_constraint }}</p>
            }
            <!-- Still show current price if present -->
            @if (rec.current_price !== null) {
              <div class="no-recommendation__current-price">
                <span class="text-micro mono uppercase">Current Price</span>
                <span class="mono">{{ CURRENCY_SYMBOL }}{{ formatNum(rec.current_price) }}</span>
              </div>
            }
          </div>
        }
      }
    </app-card>
  `,
  styleUrl: './recommendation-card.component.scss',
})
export class RecommendationCardComponent {
  recommendation = input.required<PricingRecommendation | null>();

  protected readonly CURRENCY_SYMBOL = CURRENCY_SYMBOL;

  caption = computed(() => {
    const r = this.recommendation();
    if (!r) return 'RECOMMENDATION';
    return `${r.product_id} — Pricing Recommendation`;
  });

  isIncrease = computed(() => {
    const r = this.recommendation();
    if (!r || r.recommended_price === null) return false;
    return r.recommended_price > r.current_price;
  });

  isDecrease = computed(() => {
    const r = this.recommendation();
    if (!r || r.recommended_price === null) return false;
    return r.recommended_price < r.current_price;
  });

  isKeep = computed(() => {
    const r = this.recommendation();
    if (!r || r.recommended_price === null) return false;
    return r.recommended_price === r.current_price;
  });

  isRevenuePositive = computed(() => {
    const r = this.recommendation();
    if (!r || r.revenue_change_abs === null) return true;
    return r.revenue_change_abs >= 0;
  });

  chartConfig = computed<ChartConfiguration<'bar'>>(() => {
    const r = this.recommendation();
    if (!r || !r.recommendation_available || r.expected_revenue === null) {
      return { type: 'bar', data: { labels: [], datasets: [] } };
    }

    const currentDataset: ChartDataset<'bar', number[]> = {
      label: 'Current Revenue',
      data: [r.current_revenue],
      backgroundColor: 'rgba(17, 17, 17, 0.8)',
      borderColor: '#111111',
      borderWidth: 2,
    };

    const recommendedDataset: ChartDataset<'bar', number[]> = {
      label: 'Expected Revenue',
      data: [r.expected_revenue],
      backgroundColor: this.isRevenuePositive() ? '#3CC9B4' : '#FF6B57',
      borderColor: '#111111',
      borderWidth: 2,
    };

    return {
      type: 'bar',
      data: {
        labels: ['Current Price', 'Recommended Price'],
        datasets: [currentDataset, recommendedDataset],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: {
              font: { family: "'Space Mono', monospace", size: 11 },
              boxWidth: 14,
              padding: 12,
            },
          },
          tooltip: {
            callbacks: {
              label: (item) => {
                const val = item.parsed.y;
                return ` ${item.dataset.label}: £${val != null ? val.toFixed(2) : '—'}`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { font: { family: "'Space Mono', monospace", size: 11 } },
          },
          y: {
            grid: { color: 'rgba(0,0,0,0.06)' },
            ticks: {
              font: { family: "'Space Mono', monospace", size: 10 },
              callback: (val) => `£${val}`,
            },
            title: {
              display: true,
              text: 'Weekly Revenue',
              font: { family: "'Space Mono', monospace", size: 11 },
            },
          },
        },
      },
    };
  });

  formatNum(n: number | null | undefined, decimals = 2): string {
    if (n == null) return '—';
    return n.toFixed(decimals);
  }

  formatPct(n: number | null | undefined): string {
    if (n == null) return '—';
    return (n * 100).toFixed(1) + '%';
  }
}
