/**
 * Loading state component — simple spinner or text indicator.
 */

import { Component, input } from '@angular/core';

@Component({
  selector: 'app-loading-state',
  standalone: true,
  template: `
    <div class="loading-state">
      <div class="loading-state__spinner" aria-hidden="true">⟳</div>
      <p class="loading-state__message mono">{{ message() }}</p>
    </div>
  `,
  styles: `
    .loading-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: var(--spacing-2xl);
      text-align: center;
    }

    .loading-state__spinner {
      font-size: 2rem;
      animation: spin 1.2s linear infinite;
      margin-bottom: var(--spacing-md);
      opacity: 0.6;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .loading-state__message {
      font-size: var(--font-size-small);
      opacity: 0.7;
    }
  `,
})
export class LoadingStateComponent {
  message = input<string>('Loading...');
}
