/**
 * Header component — wordmark, nav tabs, API health badge.
 * Health badge polls GET /api/health every 30 seconds.
 */

import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { ApiService } from './api.service';
import { interval, Subscription } from 'rxjs';
import { startWith, switchMap } from 'rxjs/operators';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <header class="header">
      <div class="header__container">
        <div class="header__wordmark">DEMAND & PRICING</div>

        <nav class="header__nav" aria-label="Main navigation">
          <a routerLink="/forecast" routerLinkActive="active" class="header__nav-link mono">
            Forecast
          </a>
          <a routerLink="/segments" routerLinkActive="active" class="header__nav-link mono">
            Segments
          </a>
          <a routerLink="/pricing" routerLinkActive="active" class="header__nav-link mono">
            Pricing
          </a>
        </nav>

        <div class="header__status">
          <span
            class="header__status-badge mono"
            [class.header__status-badge--online]="isOnline()"
            [class.header__status-badge--offline]="!isOnline()"
          >
            <span class="header__status-dot" aria-hidden="true"></span>
            {{ isOnline() ? 'ONLINE' : 'OFFLINE' }}
          </span>
        </div>
      </div>
    </header>
  `,
  styles: `
    .header {
      background: white;
      border-bottom: var(--border-width) solid var(--color-ink);
      box-shadow: 0 var(--shadow-offset) 0 var(--color-ink);
      position: sticky;
      top: 0;
      z-index: var(--z-header);
    }

    .header__container {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: var(--spacing-md) var(--spacing-xl);
      gap: var(--spacing-xl);
    }

    .header__wordmark {
      font-family: var(--font-heading);
      font-weight: var(--font-weight-bold);
      font-size: var(--font-size-medium);
      padding: var(--spacing-sm) var(--spacing-md);
      background: var(--color-lime);
      border: var(--border-width) solid var(--color-ink);
      border-radius: var(--border-radius);
      box-shadow: var(--shadow-base);
      text-transform: uppercase;
      letter-spacing: var(--letter-spacing-tight);
      white-space: nowrap;
    }

    .header__nav {
      display: flex;
      gap: var(--spacing-sm);
      flex: 1;
      justify-content: center;
    }

    .header__nav-link {
      padding: var(--spacing-sm) var(--spacing-lg);
      border: var(--border-width) solid var(--color-ink);
      border-radius: var(--border-radius);
      background: white;
      text-decoration: none;
      color: var(--color-ink);
      text-transform: uppercase;
      letter-spacing: var(--letter-spacing-wide);
      font-size: var(--font-size-small);
      font-weight: var(--font-weight-bold);
      transition: all var(--transition-fast);
      box-shadow: var(--shadow-base);
    }

    .header__nav-link:hover {
      transform: translate(-2px, -2px);
      box-shadow: var(--shadow-hover);
    }

    .header__nav-link:active {
      transform: translate(2px, 2px);
      box-shadow: var(--shadow-active);
    }

    .header__nav-link.active {
      background: var(--color-ink);
      color: var(--color-lime);
    }

    .header__status-badge {
      display: inline-flex;
      align-items: center;
      gap: var(--spacing-xs);
      padding: 6px var(--spacing-md);
      border: var(--border-width) solid var(--color-ink);
      border-radius: var(--border-radius);
      font-size: var(--font-size-small);
      font-weight: var(--font-weight-bold);
      text-transform: uppercase;
      letter-spacing: var(--letter-spacing-wide);
      white-space: nowrap;
    }

    .header__status-badge--online {
      background: var(--color-teal);
      color: white;
    }

    .header__status-badge--offline {
      background: var(--color-coral);
      color: white;
    }

    .header__status-dot {
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: currentColor;
    }
  `,
})
export class HeaderComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  protected isOnline = signal(false);
  private healthSubscription?: Subscription;

  ngOnInit(): void {
    // Poll health endpoint every 30 seconds
    this.healthSubscription = interval(30000)
      .pipe(
        startWith(0), // Check immediately on init
        switchMap(() => this.api.getHealth())
      )
      .subscribe({
        next: () => this.isOnline.set(true),
        error: () => this.isOnline.set(false),
      });
  }

  ngOnDestroy(): void {
    this.healthSubscription?.unsubscribe();
  }
}
