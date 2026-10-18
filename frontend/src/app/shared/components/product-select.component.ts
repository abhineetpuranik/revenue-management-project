/**
 * Product select component — shared product sidebar.
 * Shows a search input + scrollable product list with price.
 * Emits productId on click/enter.
 * Extracted from ForecastComponent for Phase 11b so the Pricing view reuses it.
 */

import { Component, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import type { Product } from '../../core/models/api.models';
import { CardComponent } from './card.component';
import { EmptyStateComponent } from './empty-state.component';
import { ErrorStateComponent } from './error-state.component';
import { LoadingStateComponent } from './loading-state.component';

@Component({
  selector: 'app-product-select',
  standalone: true,
  imports: [FormsModule, CardComponent, LoadingStateComponent, ErrorStateComponent, EmptyStateComponent],
  template: `
    <app-card caption="PRODUCT">
      <input
        type="search"
        class="product-search mono"
        placeholder="Search P001…"
        [value]="search()"
        (input)="search.set($any($event.target).value)"
        aria-label="Search products"
      />

      @if (loading()) {
        <app-loading-state message="Loading products…" />
      } @else if (error()) {
        <app-error-state [message]="error()!" [showRetry]="true" (retry)="retry.emit()" />
      } @else if (filtered().length === 0) {
        <app-empty-state message="No products match." />
      } @else {
        <ul class="product-list" role="listbox" aria-label="Products">
          @for (product of filtered(); track product.product_id) {
            <li
              role="option"
              class="product-item mono"
              [class.product-item--selected]="selectedProductId() === product.product_id"
              [attr.aria-selected]="selectedProductId() === product.product_id"
              (click)="select.emit(product.product_id)"
              (keydown.enter)="select.emit(product.product_id)"
              (keydown.space)="select.emit(product.product_id)"
              [tabindex]="0"
            >
              <span class="product-item__id">{{ product.product_id }}</span>
              <span class="product-item__price">{{ currencySymbol() }}{{ formatNum(product.base_price) }}</span>
            </li>
          }
        </ul>
      }
    </app-card>
  `,
  styles: `
    .product-search {
      width: 100%;
      padding: var(--spacing-xs) var(--spacing-sm);
      border: var(--border-width) solid var(--color-ink);
      border-radius: var(--border-radius);
      background: white;
      font-family: var(--font-mono);
      font-size: var(--font-size-small);
      margin-bottom: var(--spacing-sm);
      box-shadow: var(--shadow-base);
    }

    .product-search:focus-visible {
      outline: var(--border-width) solid var(--color-purple);
      outline-offset: 2px;
    }

    .product-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 4px;
      max-height: 300px;
      overflow-y: auto;
    }

    .product-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px var(--spacing-sm);
      border: 2px solid transparent;
      border-radius: var(--border-radius);
      cursor: pointer;
      font-family: var(--font-mono);
      font-size: var(--font-size-small);
      transition: all var(--transition-fast);
    }

    .product-item:hover {
      border-color: var(--color-ink);
      background: var(--color-lime);
    }

    .product-item--selected {
      background: var(--color-ink);
      color: var(--color-lime);
      border-color: var(--color-ink);
    }

    .product-item__id {
      font-weight: var(--font-weight-bold);
    }

    .product-item__price {
      opacity: 0.75;
    }
  `,
})
export class ProductSelectComponent {
  products = input.required<Product[]>();
  loading = input<boolean>(false);
  error = input<string | null>(null);
  selectedProductId = input.required<string>();
  currencySymbol = input<string>('£');

  select = output<string>();
  retry = output<void>();

  search = signal('');

  filtered = computed(() => {
    let list = this.products();
    const q = this.search().toLowerCase();
    if (q) list = list.filter((p) => p.product_id.toLowerCase().includes(q));
    return list;
  });

  formatNum(n: number | undefined | null, decimals = 2): string {
    if (n == null) return '—';
    return n.toFixed(decimals);
  }
}
