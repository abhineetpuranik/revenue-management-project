/**
 * Segments view — Phase 11a
 *
 * Layout:
 *   ┌───────────────────────────────────────────────────────┐
 *   │ Page header                                           │
 *   ├────────────────────────────────────────────────────── │
 *   │ 4 stat tiles: customers / k / silhouette / groups    │
 *   ├──────────────────────────────────┬───────────────────┤
 *   │ Segment summary table            │ Doughnut chart    │
 *   ├──────────────────────────────────┴───────────────────┤
 *   │ Customer lookup (single-record)                      │
 *   ├──────────────────────────────────────────────────────┤
 *   │ Paginated customer table (50/page, filter by seg)    │
 *   └──────────────────────────────────────────────────────┘
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
import { FormsModule } from '@angular/forms';
import { ChartConfiguration } from 'chart.js';

import { ApiService } from '../../core/api.service';
import type {
  CustomerSegment,
  CustomersResponse,
  SegmentsResponse,
} from '../../core/models/api.models';
import { CardComponent } from '../../shared/components/card.component';
import { ChartWrapperComponent } from '../../shared/components/chart-wrapper.component';
import { EmptyStateComponent } from '../../shared/components/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state.component';
import { LoadingStateComponent } from '../../shared/components/loading-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header.component';
import { StatTileComponent } from '../../shared/components/stat-tile.component';
import { getSegmentColor } from '../../shared/segment-color';

@Component({
  selector: 'app-segments',
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
  templateUrl: './segments.component.html',
  styleUrl: './segments.component.scss',
})
export class SegmentsComponent implements OnInit {
  private api = inject(ApiService);
  private destroyRef = inject(DestroyRef);

  // Expose Math for template
  protected readonly Math = Math;

  // ── Segments overview ─────────────────────────────────────────────────
  segments = signal<SegmentsResponse | null>(null);
  segmentsLoading = signal(true);
  segmentsError = signal<string | null>(null);

  // ── Doughnut chart ────────────────────────────────────────────────────
  doughnutConfig = computed<ChartConfiguration>(() => {
    const s = this.segments();
    if (!s) return { type: 'doughnut', data: { labels: [], datasets: [] } };
    return {
      type: 'doughnut',
      data: {
        labels: s.segments.map((seg) => this.formatLabel(seg.segment_label)),
        datasets: [
          {
            data: s.segments.map((seg) => seg.revenue_share_pct),
            backgroundColor: s.segments.map((seg) => this.getColorHex(seg.segment_label)),
            borderColor: '#111111',
            borderWidth: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '55%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              font: { family: "'Space Mono', monospace", size: 11 },
              padding: 12,
            },
          },
          tooltip: {
            callbacks: {
              label: (item) => ` ${item.label}: ${item.parsed}% of revenue`,
            },
          },
        },
      },
    };
  });

  // ── Customer lookup ───────────────────────────────────────────────────
  lookupId = '';
  lookupResult = signal<CustomerSegment | null>(null);
  lookupLoading = signal(false);
  lookupError = signal<string | null>(null);

  // ── Paginated customer table ──────────────────────────────────────────
  readonly filterLabels = ['', 'high_value', 'regular', 'occasional', 'at_risk'];
  customerFilter = signal<string>('');
  customersPage = signal(1);
  readonly customersPageSize = 50;

  customersData = signal<CustomersResponse | null>(null);
  customersLoading = signal(false);
  customersError = signal<string | null>(null);

  ngOnInit(): void {
    this.loadSegments();
    this.loadCustomers();
  }

  private loadSegments(): void {
    this.segmentsLoading.set(true);
    this.segmentsError.set(null);
    this.api
      .getSegments()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (s) => {
          this.segments.set(s);
          this.segmentsLoading.set(false);
        },
        error: (err) => {
          this.segmentsError.set(err.message ?? 'Failed to load segments.');
          this.segmentsLoading.set(false);
        },
      });
  }

  private loadCustomers(): void {
    this.customersLoading.set(true);
    this.customersError.set(null);
    const filter = this.customerFilter() || undefined;
    this.api
      .getCustomers(filter, this.customersPage(), this.customersPageSize)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (d) => {
          this.customersData.set(d);
          this.customersLoading.set(false);
        },
        error: (err) => {
          this.customersError.set(err.message ?? 'Failed to load customers.');
          this.customersLoading.set(false);
        },
      });
  }

  retrySegments(): void {
    this.loadSegments();
  }

  retryCustomers(): void {
    this.loadCustomers();
  }

  setCustomerFilter(label: string): void {
    this.customerFilter.set(label);
    this.customersPage.set(1);
    this.customersData.set(null);
    this.loadCustomers();
  }

  goToPage(page: number): void {
    this.customersPage.set(page);
    this.loadCustomers();
  }

  lookupCustomer(): void {
    const id = this.lookupId.trim().toUpperCase();
    if (!id) return;
    this.lookupLoading.set(true);
    this.lookupError.set(null);
    this.lookupResult.set(null);
    this.api
      .getCustomerSegment(id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (c) => {
          this.lookupResult.set(c);
          this.lookupLoading.set(false);
        },
        error: (err) => {
          this.lookupError.set(err.message ?? `Customer '${id}' not found.`);
          this.lookupLoading.set(false);
        },
      });
  }

  // ── Template helpers ──────────────────────────────────────────────────
  getColor(label: string): string {
    return getSegmentColor(label);
  }

  /** Hex colours for Chart.js (which needs concrete colour strings, not CSS vars) */
  getColorHex(label: string): string {
    const map: Record<string, string> = {
      high_value: '#6C4CF1',
      regular: '#3CC9B4',
      occasional: '#FFD84D',
      at_risk: '#FF6B57',
    };
    return map[label] ?? '#111111';
  }

  formatLabel(label: string): string {
    return label.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  formatNum(n: number | undefined | null, decimals = 2): string {
    if (n == null) return '—';
    return n.toFixed(decimals);
  }

  /** Scale a percentage to a pixel bar width (max 120px at 100%) */
  barWidth(pct: number): number {
    return Math.round((pct / 100) * 120);
  }
}
