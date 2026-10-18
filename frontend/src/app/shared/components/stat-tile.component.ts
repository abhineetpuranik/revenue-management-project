/**
 * Stat tile component — large number with label in a colored block.
 */

import { Component, input } from '@angular/core';

@Component({
  selector: 'app-stat-tile',
  standalone: true,
  template: `
    <div class="stat-tile" [style.background-color]="bgColor()">
      <div class="stat-tile__value mono">{{ value() }}</div>
      <div class="stat-tile__label text-micro mono uppercase">{{ label() }}</div>
    </div>
  `,
  styles: `
    .stat-tile {
      border: var(--border-width) solid var(--color-ink);
      border-radius: var(--border-radius);
      padding: var(--spacing-md) var(--spacing-lg);
      box-shadow: var(--shadow-base);
      min-width: 140px;
    }

    .stat-tile__value {
      font-size: var(--font-size-xlarge);
      font-weight: var(--font-weight-bold);
      line-height: var(--line-height-tight);
      margin-bottom: var(--spacing-xs);
    }

    .stat-tile__label {
      opacity: 0.7;
    }
  `,
})
export class StatTileComponent {
  value = input.required<string | number>();
  label = input.required<string>();
  bgColor = input<string>('var(--color-lime)');
}
