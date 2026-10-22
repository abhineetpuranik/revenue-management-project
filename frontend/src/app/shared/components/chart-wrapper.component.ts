/**
 * Chart wrapper component — generic Chart.js container.
 * Manages chart creation, update, and destruction to prevent memory leaks.
 *
 * Key design: the effect() owns the full chart lifecycle. It destroys and
 * recreates the chart every time the config signal changes, which correctly
 * handles the case where the config arrives before AND after ngAfterViewInit.
 */

import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  ViewChild,
  effect,
  input,
} from '@angular/core';
import {
  ArcElement,
  BarController,
  BarElement,
  CategoryScale,
  Chart,
  ChartConfiguration,
  ChartType,
  DoughnutController,
  Filler,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Title,
  Tooltip,
} from 'chart.js';

// Register all Chart.js components used across the app (called once at import time)
Chart.register(
  LineController,
  BarController,
  DoughnutController,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

@Component({
  selector: 'app-chart-wrapper',
  standalone: true,
  template: `
    <div class="chart-wrapper">
      <canvas #chartCanvas></canvas>
    </div>
  `,
  styles: `
    .chart-wrapper {
      position: relative;
      width: 100%;
      height: 100%;
      min-height: 260px;
    }

    canvas {
      display: block;
    }
  `,
})
export class ChartWrapperComponent implements AfterViewInit, OnDestroy {
  @ViewChild('chartCanvas', { static: true })
  canvasRef!: ElementRef<HTMLCanvasElement>;

  config = input.required<ChartConfiguration>();

  private chart: Chart | null = null;
  private ready = false;   // true once ngAfterViewInit has run

  constructor() {
    // Runs every time config() changes. On first load this fires during
    // construction (before ngAfterViewInit), so we defer via setTimeout(0).
    // On subsequent changes (product switch, etc.) ngAfterViewInit has
    // already run and ready=true, so we recreate immediately.
    effect(() => {
      const cfg = this.config();   // subscribe to signal
      if (!this.ready) {
        // Canvas not in DOM yet — defer until after ngAfterViewInit
        setTimeout(() => this.buildChart(cfg), 0);
      } else {
        this.buildChart(cfg);
      }
    });
  }

  ngAfterViewInit(): void {
    this.ready = true;
    // Build now in case the effect already fired but was deferred
    this.buildChart(this.config());
  }

  ngOnDestroy(): void {
    this.destroyChart();
  }

  private buildChart(cfg: ChartConfiguration): void {
    // Skip if there is no data worth drawing
    if (!cfg.data?.datasets?.length) {
      return;
    }

    let ctx: CanvasRenderingContext2D | null = null;
    try {
      ctx = this.canvasRef?.nativeElement?.getContext('2d') ?? null;
    } catch {
      return; // SSR / jsdom — canvas not implemented
    }
    if (!ctx) return;

    // Destroy the previous instance before creating a new one
    this.destroyChart();

    try {
      this.chart = new Chart(ctx, {
        type: cfg.type as ChartType,
        data: cfg.data,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          ...(cfg.options ?? {}),
        },
      });
    } catch (err) {
      console.error('ChartWrapper: failed to create chart', err);
    }
  }

  private destroyChart(): void {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }
}
