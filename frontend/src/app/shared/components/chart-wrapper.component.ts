/**
 * Chart wrapper component — generic Chart.js container.
 * Manages chart creation, update, and destruction to prevent memory leaks.
 * Registers only the Chart.js components actually needed.
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
  Chart,
  ChartConfiguration,
  ChartType,
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
} from 'chart.js';

// Register Chart.js components used across the app
Chart.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
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
      min-height: 300px;
    }

    canvas {
      max-width: 100%;
    }
  `,
})
export class ChartWrapperComponent implements AfterViewInit, OnDestroy {
  @ViewChild('chartCanvas', { static: true }) canvasRef!: ElementRef<HTMLCanvasElement>;

  config = input.required<ChartConfiguration>();
  private chart: Chart | null = null;

  constructor() {
    // React to config changes and update the chart
    effect(() => {
      const newConfig = this.config();
      if (this.chart) {
        // Update existing chart
        this.chart.data = newConfig.data;
        this.chart.options = newConfig.options ?? {};
        this.chart.update();
      }
    });
  }

  ngAfterViewInit(): void {
    this.createChart();
  }

  ngOnDestroy(): void {
    this.destroyChart();
  }

  private createChart(): void {
    if (!this.canvasRef) {
      return;
    }

    const ctx = this.canvasRef.nativeElement.getContext('2d');
    if (!ctx) {
      return;
    }

    const config = this.config();

    // Graceful handling of empty data
    if (!config.data || !config.data.datasets || config.data.datasets.length === 0) {
      console.warn('ChartWrapper: No datasets provided, chart will not render');
      return;
    }

    try {
      this.chart = new Chart(ctx, {
        type: config.type as ChartType,
        data: config.data,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          ...(config.options ?? {}),
          font: {
            family: "'Space Mono', monospace",
          },
        },
      });
    } catch (error) {
      console.error('ChartWrapper: Failed to create chart', error);
    }
  }

  private destroyChart(): void {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }
}
