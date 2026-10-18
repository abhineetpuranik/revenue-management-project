# Frontend — Angular 21 Dashboard

Neo-brutalist bento-grid dashboard for the AI-Powered Demand Forecasting & Dynamic Pricing project. Displays forecast, segmentation, and pricing data from the Flask API.

---

## Quick start

```bash
# From repo root: ensure the Flask backend is running first
cd backend && python app.py   # → http://localhost:5000

# In a separate terminal
cd frontend
npm install
npm start   # → http://localhost:4200
```

The app redirects `/` → `/forecast` on load.

---

## Views

| Route | Status | Description |
|---|---|---|
| `/forecast` | ✅ Live | Product sidebar (shared components), category chips, Chart.js line chart (history + test window), MAPE/RMSE/MAE tiles, model comparison table, weekly data table |
| `/segments` | ✅ Live | Stat tiles (customers / k / silhouette), segment summary table with bar charts, revenue doughnut, customer lookup, paginated customer table with segment filter |
| `/pricing` | ✅ Live | Product sidebar, category chips, recommendation card with bar chart + direction tag + revenue tiles, explanation panel with source badge, paginated recommendations table with row-click selection |

---

## Tech stack

| Tool | Version | Purpose |
|---|---|---|
| Angular | 21 | Framework — standalone components, signals |
| TypeScript | 5.9 | Strict mode |
| Chart.js | 4.5 | Line chart (forecast), bar chart (pricing), doughnut (segments) |
| Space Grotesk | 700 | Heading font |
| Space Mono | 400 | Body / mono font |
| Vitest | 4 | Unit tests (76 tests across 10 spec files) |

---

## Project structure

```
src/
├── app/
│   ├── app.ts / app.html / app.scss     Root component (header + router-outlet + footer)
│   ├── app.routes.ts                    Lazy-loaded routes
│   ├── app.config.ts                    provideRouter + provideHttpClient(withFetch)
│   ├── core/
│   │   ├── api.service.ts               Typed HTTP client for all Phase 10a + 10b endpoints
│   │   ├── header.component.ts          Sticky header: nav + health badge (polls /api/health every 30s)
│   │   ├── models/
│   │   │   └── api.models.ts            TypeScript interfaces (forecast, segments, pricing, explanations)
│   │   └── tests/
│   │       ├── api.service.spec.ts      10 tests (Phase 10a endpoints)
│   │       └── api-pricing.service.spec.ts  6 tests (Phase 10b endpoints)
│   ├── shared/
│   │   ├── segment-color.ts             getSegmentColor() pure helper
│   │   ├── components/
│   │   │   ├── page-header.component.ts
│   │   │   ├── card.component.ts
│   │   │   ├── stat-tile.component.ts
│   │   │   ├── tag.component.ts
│   │   │   ├── category-chips.component.ts   Shared category filter (Forecast + Pricing)
│   │   │   ├── product-select.component.ts   Shared product sidebar (Forecast + Pricing)
│   │   │   ├── explanation-panel.component.ts Reusable LLM explanation display (4 states)
│   │   │   ├── loading-state.component.ts
│   │   │   ├── error-state.component.ts
│   │   │   ├── empty-state.component.ts
│   │   │   └── chart-wrapper.component.ts    Chart.js lifecycle manager
│   │   └── tests/
│   │       ├── segment-color.spec.ts    7 tests
│   │       ├── loading-state.spec.ts    8 tests (covers loading / error / empty)
│   │       ├── stat-tile.spec.ts        4 tests
│   │       └── explanation-panel.spec.ts  11 tests (4 states + plain-text rendering)
│   └── features/
│       ├── forecast/                    Forecast view (uses shared category/product)
│       ├── segments/                    Segmentation view
│       └── pricing/                     Pricing view
│           ├── pricing.component.*       Orchestrator (stale guard + explanation timeout)
│           ├── recommendation-card.*     Single product recommendation
│           └── recommendations-table.*   Paginated overview table
├── environments/
│   ├── environment.ts                   dev: apiBaseUrl = http://localhost:5000
│   └── environment.prod.ts
└── styles/
    └── tokens.scss                      CSS custom properties (colors, spacing, shadows)
```

---

## Running tests

```bash
npm test
# → 76 tests across 10 spec files, all passing
```

---

## Design system

All visual tokens are CSS custom properties defined in `src/styles/tokens.scss`.

| Token | Value | Use |
|---|---|---|
| `--color-background` | `#F4F1EA` | Page background |
| `--color-ink` | `#111111` | Text, borders, shadows |
| `--color-lime` | `#C6F24E` | Primary accent, active states |
| `--color-purple` | `#6C4CF1` | high_value segment, selected model |
| `--color-teal` | `#3CC9B4` | regular segment, success states |
| `--color-yellow` | `#FFD84D` | occasional segment, warnings |
| `--color-coral` | `#FF6B57` | at_risk segment, error states |
| `--shadow-base` | `5px 5px 0 #111` | Hard brutalist shadow |
| `--border-width` | `3px` | Consistent border weight |

---

## Phase 12 TODO

- Add segment explanation cards to the Segments view using the existing
  `ExplanationPanelComponent` and `ApiService.getSegmentExplanation()` (both
  are ready, just need to wire them in the Segments component).
- Wire forecast explanation handling — `GET /api/forecast/<id>/explanation`
  always returns `explanation_available: false`, so it can be a silent no-op
  or a small "not available" note.
- End-to-end integration testing with real backend + MySQL.
