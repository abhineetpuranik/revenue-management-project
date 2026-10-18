/**
 * Empty state component — no data to display message.
 */

import { Component, input } from '@angular/core';

@Component({
  selector: 'app-empty-state',
  standalone: true,
  template: `
    <div class="empty-state">
      <p class="empty-state__message mono">{{ message() }}</p>
    </div>
  `,
  styles: `
    .empty-state {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: var(--spacing-2xl);
      text-align: center;
      opacity: 0.6;
    }

    .empty-state__message {
      font-size: var(--font-size-base);
      max-width: 50ch;
    }
  `,
})
export class EmptyStateComponent {
  message = input<string>('No data available.');
}
