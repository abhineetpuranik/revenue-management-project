/**
 * Card component — bordered block with optional caption and colored background.
 */

import { Component, input } from '@angular/core';

@Component({
  selector: 'app-card',
  standalone: true,
  template: `
    <div class="card" [class.card--colored]="bgColor()" [style.background-color]="bgColor()">
      @if (caption()) {
        <div class="card__caption text-micro mono">{{ caption() }}</div>
      }
      <ng-content />
    </div>
  `,
  styles: `
    .card {
      background: white;
      border: var(--border-width) solid var(--color-ink);
      border-radius: var(--border-radius);
      padding: var(--spacing-lg);
      box-shadow: var(--shadow-base);
    }

    .card--colored {
      color: var(--color-ink);
    }

    .card__caption {
      margin-bottom: var(--spacing-sm);
      opacity: 0.6;
    }
  `,
})
export class CardComponent {
  caption = input<string>();
  bgColor = input<string>('');  // CSS color value or empty for white
}
