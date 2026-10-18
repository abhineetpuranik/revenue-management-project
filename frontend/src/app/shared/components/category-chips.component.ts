/**
 * Category chips component — shared filter buttons.
 * Emits the selected category string ('All' = no filter).
 * Extracted from ForecastComponent for Phase 11b so the Pricing view reuses it.
 */

import { Component, input, output } from '@angular/core';

@Component({
  selector: 'app-category-chips',
  standalone: true,
  template: `
    <div class="category-chips">
      @for (cat of categories(); track cat) {
        <button
          type="button"
          class="chip mono"
          [class.chip--active]="selected() === cat"
          (click)="select.emit(cat)"
        >
          {{ cat }}
        </button>
      }
    </div>
  `,
  styles: `
    .category-chips {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-xs);
    }

    .chip {
      padding: var(--spacing-xs) var(--spacing-sm);
      border: var(--border-width) solid var(--color-ink);
      border-radius: var(--border-radius);
      background: white;
      font-family: var(--font-mono);
      font-size: var(--font-size-small);
      text-align: left;
      text-transform: uppercase;
      letter-spacing: var(--letter-spacing-wide);
      transition: all var(--transition-fast);
      box-shadow: var(--shadow-base);
      cursor: pointer;
    }

    .chip:hover {
      transform: translate(-2px, -2px);
      box-shadow: var(--shadow-hover);
    }

    .chip--active {
      background: var(--color-ink);
      color: var(--color-lime);
    }
  `,
})
export class CategoryChipsComponent {
  categories = input.required<string[]>();
  selected = input.required<string>();
  select = output<string>();
}
