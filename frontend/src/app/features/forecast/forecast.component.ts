/**
 * Forecast view — Phase 11a
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────────┐
 *   │ Page header                                         │
 *   ├──────────────┬──────────────────────────────────────┤
 *   │ Left sidebar │ Chart area (history + test)          │
 *   │  ▸ Category  │                                      │
 *   │    chips     ├──────────────────────────────────────┤
 *   │  ▸ Product   │ Metric tiles: MAE · MAPE · RMSE     │
 *   │    list      ├──────────────────────────────────────┤
 *   │              │ Model comparison table               │
 *   │              ├──────────────────────────────────────┤
 *   │              │ Weekly data table                    │
 *   └──────────────┴──────────────────────────────────────┘
 */

import {
  Component,
  OnInit,
  computed,
  inject,
  signal,
  DestroyRef,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ChartConfiguration, ScriptableContext, ChartDataset } from 'chart.js';

import { ApiService } from '../../core/api.service';
import type {
  ForecastDataPoint,
  ForecastMetrics,
  ForecastResponse,
  Product,
} from '../../core/models/api.models';
import { CardComponent } from '../../shared/components/card.component';
import { ChartWrapperComponent } from '../../shared/components/chart-wrapper.component';
import { EmptyStateComponent } from '../../shared/components/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state.component';
import { LoadingStateComponent } from '../../shared/components/loading-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header.component';
import { StatTileComponent } from '../../shared/components/stat-tile.component';

const CATEGORIES = ['All', 'Staples', 'Personal Care', 'Electronics', 'Clothing', 'Impulse'];

@Component({
  selector: 'app-forecast',
  standalone: true,
  imports: [
    FormsModule,
    PageHeaderComponent,
    CardComponent,
    StatTileComponent,
    ChartWrapperComponent,
    LoadingStateComponent,
    ErrorStateComponent,
    EmptyStateComponent,
  ],
  templateUrl: './forecast.component.html',
  styleUrl: './forecast.component.scss',
})
export class ForecastComponent implements OnInit {
  private api = inject(ApiService);
  private destroyRef = inject(DestroyRef);

  // ── Product catalog ───────────────────────────────────────────────────
  products = signal<Product[]>([]);
  productsLoading = signal(true);
  productsError = signal<string | null>(null);

  selectedCategory = signal<string>('All');
  selectedProductId = signal<string>('');
  productSearch = signal<string>('');

  readonly categories = CATEGORIES;

  filteredProducts = computed(() => {
    let list = this.products();
    const cat = this.selectedCategory();
    const q = this.productSearch().toLowerCase();
    if (cat !== 'All') list = list.filter((p) => p.category === cat);
    if (q) list = list.filter((p) => p.product_id.toLowerCase().includes(q));
    return list;
  });

  selectedProduct = computed(() =>
    this.products().find((p) => p.product_id === this.selectedProductId()) ?? null
  );

  // ── Global metrics ────────────────────────────────────────────────────
  metrics = signal<ForecastMetrics | null>(null);
  metricsLoading = signal(true);
  metricsError = signal<string | null>(null);

  // ── Per-product forecast ──────────────────────────────────────────────
  forecast = signal<ForecastResponse | null>(null);
  forecastLoading = signal(false);
  forecastError = signal<string | null>(null);

  // ── Chart configuration ───────────────────────────────────────────────
  chartConfig = computed<ChartConfiguration<'line'>>(() => {
    const f = this.forecast();
    if (!f) return this.emptyChartConfig();
    return this.buildChartConfig(f);
  });

  // ── Model comparison rows ─────────────────────────────────────────────
  modelRows = computed(() => {
    const m = this.metrics();
    if (!m) return [];
    const isSelected = (name: string) => name === m.selected_model;
    return [
      {
        name: 'Linear Regression',
        key: 'LinearRegression',
        mae: m.models.LinearRegression.mae,
        mape: m.models.LinearRegression.mape,
        rmse: m.models.LinearRegression.rmse,
        selected: isSelected('LinearRegression'),
      },
      {
        name: 'XGBoost',
        key: 'XGBoost',
        mae: m.models.XGBoost.mae,
        mape: m.models.XGBoost.mape,
        rmse: m.models.XGBoost.rmse,
        selected: isSelected('XGBoost'),
      },
    ];
  });

  // ── Selected model metrics (for stat tiles) ───────────────────────────
  selectedMetrics = computed(() => {
    const m = this.metrics();
    if (!m) return null;
    const key = m.selected_model as 'LinearRegression' | 'XGBoost';
    return m.models[key];
  });

  ngOnInit(): void {
    this.loadProducts();
    this.loadMetrics();
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
          // Auto-select first product
          if (products.length > 0 && !this.selectedProductId()) {
            this.selectProduct(products[0].product_id);
          }
        },
        error: (err) => {
          this.productsError.set(err.message ?? 'Failed to load products.');
          this.productsLoading.set(false);
        },
      });
  }

  private loadMetrics(): void {
    this.metricsLoading.set(true);
    this.metricsError.set(null);
    this.api
      .getForecastMetrics()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (m) => {
          this.metrics.set(m);
          this.metricsLoading.set(false);
        },
        error: (err) => {
          this.metricsError.set(err.message ?? 'Failed to load forecast metrics.');
          this.metricsLoading.set(false);
        },
      });
  }

  selectCategory(cat: string): void {
    this.selectedCategory.set(cat);
    // If the currently selected product is not in this category, select the first match
    const filtered = this.filteredProducts();
    if (!filtered.find((p) => p.product_id === this.selectedProductId()) && filtered.length > 0) {
      this.selectProduct(filtered[0].product_id);
    }
  }

  selectProduct(productId: string): void {
    this.selectedProductId.set(productId);
    this.loadForecast(productId);
  }

  retryProducts(): void {
    this.loadProducts();
  }

  retryMetrics(): void {
    this.loadMetrics();
  }

  retryForecast(): void {
    const id = this.selectedProductId();
    if (id) this.loadForecast(id);
  }

  private loadForecast(productId: string): void {
    this.forecastLoading.set(true);
    this.forecastError.set(null);
    this.forecast.set(null);
    this.api
      .getForecast(productId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (f) => {
          this.forecast.set(f);
          this.forecastLoading.set(false);
        },
        error: (err) => {
          this.forecastError.set(err.message ?? 'Failed to load forecast data.');
          this.forecastLoading.set(false);
        },
      });
  }

  private buildChartConfig(f: ForecastResponse): ChartConfiguration<'line'> {
    const history = f.series.filter((d) => d.row_type === 'history');

    // Labels span the full series
    const labels = f.series.map((d) => this.formatWeekLabel(d));

    // Actual units — full series
    const actualData = f.series.map((d) => d.actual_units);

    // Predicted units — only test rows; history slots get null
    const predictedData: (number | null)[] = f.series.map((d) =>
      d.row_type === 'test' && d.predicted_units != null ? d.predicted_units : null
    );

    // Bridge point: last history point colouring changes to test-window colour
    const bridgeIndex = history.length - 1;

    const actualDataset: ChartDataset<'line', number[]> = {
      label: 'Actual Units',
      data: actualData,
      borderColor: '#111111',
      backgroundColor: 'rgba(17,17,17,0.06)',
      borderWidth: 2.5,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: (ctx: ScriptableContext<'line'>) =>
        ctx.dataIndex <= bridgeIndex ? '#C6F24E' : '#3CC9B4',
      pointBorderColor: '#111111',
      pointBorderWidth: 2,
      tension: 0.3,
      fill: false,
    };

    const predictedDataset: ChartDataset<'line', (number | null)[]> = {
      label: 'Predicted Units (XGBoost)',
      data: predictedData,
      borderColor: '#6C4CF1',
      backgroundColor: 'rgba(108,76,241,0.08)',
      borderWidth: 2.5,
      borderDash: [6, 3],
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: '#6C4CF1',
      pointBorderColor: '#111111',
      pointBorderWidth: 2,
      spanGaps: false,
      tension: 0.3,
      fill: false,
    };

    return {
      type: 'line',
      data: {
        labels,
        datasets: [actualDataset, predictedDataset],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            position: 'top',
            labels: {
              font: { family: "'Space Mono', monospace", size: 11 },
              boxWidth: 16,
              padding: 16,
            },
          },
          tooltip: {
            callbacks: {
              title: (items) => items[0]?.label ?? '',
              label: (item) => {
                if (item.parsed.y === null) return '';
                return ` ${item.dataset.label}: ${item.parsed.y} units`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: 'rgba(0,0,0,0.04)' },
            ticks: {
              font: { family: "'Space Mono', monospace", size: 10 },
              maxRotation: 45,
            },
          },
          y: {
            grid: { color: 'rgba(0,0,0,0.06)' },
            ticks: {
              font: { family: "'Space Mono', monospace", size: 11 },
            },
            title: {
              display: true,
              text: 'Units / Week',
              font: { family: "'Space Mono', monospace", size: 11 },
            },
          },
        },
      },
    };
  }

  private emptyChartConfig(): ChartConfiguration<'line'> {
    return {
      type: 'line',
      data: { labels: [], datasets: [] },
      options: { responsive: true, maintainAspectRatio: false },
    };
  }

  private formatWeekLabel(d: ForecastDataPoint): string {
    return `W${d.iso_week}`;
  }

  // ── Template helpers ──────────────────────────────────────────────────
  formatNum(n: number | undefined | null, decimals = 2): string {
    if (n == null) return '—';
    return n.toFixed(decimals);
  }

  formatPct(n: number | undefined | null): string {
    if (n == null) return '—';
    return n.toFixed(1) + '%';
  }
}
