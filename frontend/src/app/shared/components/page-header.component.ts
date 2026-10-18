/**
 * Page header component — label + title + optional description.
 * Example: label="[ 01 / FORECAST ]" title="Demand Forecast"
 */

import { Component, input } from '@angular/core';

@Component({
  selector: 'app-page-header',
  standalone: true,
  template: `
    <header class="page-header">
      @if (label()) {
        <div class="page-header__label text-micro mono">{{ label() }}</div>
      }
      <h1 class="page-header__title">{{ title() }}</h1>
      @if (description()) {
        <p class="page-header__description mono">{{ description() }}</p>
      }
    </header>
  `,
  styles: `
    .page-header {
      margin-bottom: var(--spacing-xl);
    }

    .page-header__label {
      color: var(--color-ink);
      opacity: 0.6;
      margin-bottom: var(--spacing-xs);
    }

    .page-header__title {
      font-size: var(--font-size-large);
      margin-bottom: var(--spacing-sm);
    }

    .page-header__description {
      font-size: var(--font-size-base);
      opacity: 0.8;
      max-width: 60ch;
    }
  `,
})
export class PageHeaderComponent {
  label = input<string>();
  title = input.required<string>();
  description = input<string>();
}
