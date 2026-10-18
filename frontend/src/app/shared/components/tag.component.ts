/**
 * Tag/badge component — small labeled pill with colored background.
 */

import { Component, input } from '@angular/core';

@Component({
  selector: 'app-tag',
  standalone: true,
  template: `
    <span class="tag mono" [style.background-color]="bgColor()" [style.color]="textColor()">
      {{ label() }}
    </span>
  `,
  styles: `
    .tag {
      display: inline-block;
      font-size: var(--font-size-small);
      padding: 2px var(--spacing-sm);
      border: var(--border-width) solid var(--color-ink);
      border-radius: var(--border-radius);
      text-transform: uppercase;
      letter-spacing: var(--letter-spacing-wide);
      font-weight: var(--font-weight-bold);
    }
  `,
})
export class TagComponent {
  label = input.required<string>();
  bgColor = input<string>('var(--color-lime)');
  textColor = input<string>('var(--color-ink)');
}
