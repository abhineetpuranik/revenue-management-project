/**
 * Error state component — displays error message with optional retry button.
 */

import { Component, input, output } from '@angular/core';

@Component({
  selector: 'app-error-state',
  standalone: true,
  template: `
    <div class="error-state">
      <div class="error-state__icon" aria-hidden="true">⚠</div>
      <p class="error-state__message mono">{{ message() }}</p>
      @if (showRetry()) {
        <button type="button" class="error-state__retry" (click)="retry.emit()">
          Retry
        </button>
      }
    </div>
  `,
  styles: `
    .error-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: var(--spacing-2xl);
      text-align: center;
      background-color: rgba(255, 107, 87, 0.1);
      border: var(--border-width) solid var(--color-coral);
      border-radius: var(--border-radius);
    }

    .error-state__icon {
      font-size: 2rem;
      margin-bottom: var(--spacing-md);
      color: var(--color-coral);
    }

    .error-state__message {
      font-size: var(--font-size-base);
      margin-bottom: var(--spacing-md);
      max-width: 50ch;
    }

    .error-state__retry {
      font-family: var(--font-mono);
      font-size: var(--font-size-small);
      padding: var(--spacing-sm) var(--spacing-lg);
      background: var(--color-coral);
      color: white;
      border: var(--border-width) solid var(--color-ink);
      border-radius: var(--border-radius);
      box-shadow: var(--shadow-base);
      text-transform: uppercase;
      letter-spacing: var(--letter-spacing-wide);
      transition: all var(--transition-fast);
    }

    .error-state__retry:hover {
      transform: translate(-2px, -2px);
      box-shadow: var(--shadow-hover);
    }

    .error-state__retry:active {
      transform: translate(2px, 2px);
      box-shadow: var(--shadow-active);
    }
  `,
})
export class ErrorStateComponent {
  message = input.required<string>();
  showRetry = input<boolean>(true);
  retry = output<void>();
}
