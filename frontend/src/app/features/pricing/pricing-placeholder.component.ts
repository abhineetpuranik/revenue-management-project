/**
 * Pricing placeholder view — Phase 11a.
 * Phase 10b endpoints (/api/pricing, /api/explanations) will be wired up
 * in Phase 11b. This view signals that the route exists but the data layer
 * is not connected yet.
 */

import { Component } from '@angular/core';
import { CardComponent } from '../../shared/components/card.component';
import { PageHeaderComponent } from '../../shared/components/page-header.component';
import { StatTileComponent } from '../../shared/components/stat-tile.component';

@Component({
  selector: 'app-pricing-placeholder',
  standalone: true,
  imports: [PageHeaderComponent, CardComponent, StatTileComponent],
  template: `
    <app-page-header
      label="[ 03 / PRICING ]"
      title="Pricing Recommendations"
      description="XGBoost-elasticity price optimiser — Phase 10b endpoints"
    />

    <div class="teaser-grid">
      <app-stat-tile
        value="+7.9%"
        label="Expected Revenue Uplift"
        bgColor="var(--color-lime)"
      />
      <app-stat-tile
        value="50"
        label="Products Optimised"
        bgColor="var(--color-teal)"
      />
      <app-stat-tile
        value="48 / 50"
        label="Correct Price Directions"
        bgColor="var(--color-purple)"
      />
      <app-stat-tile
        value="±15%"
        label="Max Price Change Cap"
        bgColor="var(--color-pink)"
      />
    </div>

    <app-card caption="COMING IN PHASE 11b">
      <div class="placeholder-body">
        <p class="mono">
          This view will display per-product pricing recommendations
          from <code>GET /api/pricing/&lt;product_id&gt;</code> and
          LLM-generated explanations from <code>GET /api/pricing/&lt;product_id&gt;/explanation</code>.
        </p>
        <ul class="feature-list mono">
          <li>Paginated recommendations table with category filter</li>
          <li>Price change indicator (raise / lower / no change)</li>
          <li>Constraint badges (MARGIN · MAX_CHANGE · STOCK)</li>
          <li>Expected revenue delta vs current</li>
          <li>Inline LLM explanation with source badge (LLM / fallback / mock)</li>
          <li>Segment explanation cards</li>
        </ul>

        <div class="constraint-preview">
          <p class="constraint-preview__label mono text-micro">Constraints applied by Phase 8</p>
          <div class="constraint-chips">
            <span class="constraint-chip mono">min_margin_pct: 10%</span>
            <span class="constraint-chip mono">max_price_change_pct: ±15%</span>
          </div>
        </div>
      </div>
    </app-card>
  `,
  styles: `
    .teaser-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: var(--spacing-md);
      margin-bottom: var(--spacing-lg);

      @media (max-width: 900px) {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    .placeholder-body {
      p {
        line-height: var(--line-height-relaxed);
        margin-bottom: var(--spacing-md);

        code {
          background: rgba(0, 0, 0, 0.06);
          padding: 2px 6px;
          border-radius: 4px;
          font-family: var(--font-mono);
        }
      }
    }

    .feature-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: var(--spacing-xs);
      margin-bottom: var(--spacing-lg);

      li::before {
        content: '▸ ';
        color: var(--color-purple);
      }
    }

    .constraint-preview {
      border-top: 2px solid rgba(0, 0, 0, 0.08);
      padding-top: var(--spacing-md);
    }

    .constraint-preview__label {
      margin-bottom: var(--spacing-sm);
      opacity: 0.6;
    }

    .constraint-chips {
      display: flex;
      gap: var(--spacing-sm);
      flex-wrap: wrap;
    }

    .constraint-chip {
      display: inline-block;
      padding: 4px var(--spacing-md);
      border: var(--border-width) solid var(--color-ink);
      border-radius: var(--border-radius);
      background: var(--color-yellow);
      font-size: var(--font-size-small);
      box-shadow: var(--shadow-base);
    }
  `,
})
export class PricingPlaceholderComponent {}
