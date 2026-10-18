# Phase 11a + 11b — Angular Dashboard

## Deliverables

Phase 11a implemented the app shell, design system, Forecast view, and Segmentation view.
Phase 11b replaced the Pricing placeholder with the full Pricing view, adds reusable shared
components extracted from Phase 11a code, and extends api.service.ts for all Phase 10b
endpoints.

---

## Build & test results (Phase 11b final state)

| Step | Command | Result |
|---|---|---|
| Build (dev) | `ng build --configuration development` | ✅ 0 errors, 0 warnings |
| Tests | `ng test --include="src/**/*.spec.ts" --watch=false` | ✅ 76 tests, 10 files, 0 failures |
| Bundles (lazy) | — | forecast: 41 kB, segments: 50 kB, pricing: 103 kB |

---

## Views

| Route | Status | Description |
|---|---|---|
| `/forecast` | ✅ Live | Product sidebar, category chips, Chart.js line chart (history + test window), MAPE/RMSE/MAE tiles, model comparison table, weekly data table |
| `/segments` | ✅ Live | Stat tiles (customers / k / silhouette), segment summary table with bar charts, revenue doughnut, customer lookup, paginated customer table with segment filter |
| `/pricing` | ✅ Live | Product sidebar, category chips, recommendation card with bar chart, explanation panel, paginated recommendations table |

---

## Architecture decisions

**Standalone components everywhere.** All components use `standalone: true` and declare their
own `imports[]`.

**Signals for state management.** `signal()`, `computed()`, and `effect()` from Angular 21's
reactivity primitives. State reads are explicit; no `async` pipes or `BehaviorSubject` chains.

**`takeUntilDestroyed(destroyRef)`** for HTTP subscriptions. Subscriptions are cancelled when
a component is destroyed. The `HeaderComponent` uses `OnDestroy` + manual unsubscribe because
it runs `interval()`.

**Stale-response guard.** `PricingComponent` maintains separate `recToken` and `expToken`
counters. Each new product selection increments both counters. A subscriber only writes to
signals when its captured token still equals the current counter — older in-flight responses
are silently discarded. This prevents stale data appearing when the user rapidly switches
products.

**Explanation timeout.** `EXPLANATION_TIMEOUT_MS = 35_000` (35 seconds, ~5 s above the
backend LLM timeout). A `timer()` observable races against the HTTP call. If the state is
still `'loading'` after the timer fires, the explanation panel transitions to `'error'` with a
"timed out" message and shows a Retry button. The number and reason are always shown regardless
— the explanation never blocks the recommendation card.

**Chart.js registered once.** `ChartWrapperComponent` registers all used Chart.js components
on import. A try/catch around `canvas.getContext('2d')` handles SSR/jsdom environments
gracefully.

**Lazy-loaded routes.** All three feature components are lazy-loaded via `loadComponent()`.

**CSS custom properties for theming.** All design tokens live in `src/styles/tokens.scss`.
Chart.js datasets use concrete hex values (required by Chart.js API), but all other components
reference tokens via `var(--color-*)`.

**Currency.** `£` (pound sterling) confirmed from `docs/api.md` field glossary ("Total spend
(£)") and existing Segments view. Defined as `const CURRENCY_SYMBOL = '£'` in each component
that uses it.

**Font loading.** Fontsource CSS files listed in `angular.json` → `styles[]` because Sass
`@use` does not accept plain CSS files.

---

## Explanation panel states

| State | When | Displayed |
|---|---|---|
| `loading` | HTTP call in flight | Spinner + "GENERATING EXPLANATION…" |
| `available` | `explanation_available: true` and `explanation` present | Yellow block, plain-text explanation, source badge, caption |
| `unavailable` | `explanation_available: false` | Neutral message with `unavailable_reason` from API |
| `error` | HTTP error or timeout | Error state with Retry button; reason shown |

The `source` badge is colour-coded: teal = `llm`, yellow = `fallback`, pink = `mock`.

The explanation is rendered via Angular interpolation (`{{ text() }}`), never via `innerHTML`
or `[innerHtml]`. Markup in LLM output (e.g. `<b>text</b>`) appears as literal characters.

---

## Recommendation card states

| `recommendation_available` | Display |
|---|---|
| `true` | Full card: current/recommended prices, direction tag (INCREASE/DECREASE/KEEP), revenue tiles with £ delta + percent, bar chart, elasticity + helper text, constraints, reason codes, details grid |
| `false` | Non-error neutral block with `no_candidate_reason`, `binding_constraint`, and whatever current-price information the response contains |

The direction tag and colour of the revenue change are independent signals — both an arrow
character (↑/↓) and a CSS class indicate direction, so the view is never colour-only.

---

## Data flow — Pricing view

```
PricingComponent (orchestrator)
│
├── ngOnInit()
│   ├── loadProducts()          → GET /api/products
│   └── loadTable()             → GET /api/pricing/recommendations?page=1&page_size=50
│
├── selectProduct(id)
│   ├── loadRecommendation(id)  → GET /api/pricing/<id>         (recToken guard)
│   └── loadExplanation(id)     → GET /api/pricing/<id>/explanation  (expToken guard + 35s timeout)
│
├── selectCategory(cat)
│   ├── [re-select first product if current not in category]
│   └── loadTable()             → GET /api/pricing/recommendations?category=<cat>&page=1
│
└── selectProductFromTable(id)  → calls selectProduct(id) + scroll to #pricing-detail
```

---

## API usage — Phase 10b endpoints

All HTTP goes through `ApiService`. No component calls `HttpClient` directly.

| Method | Endpoint |
|---|---|
| `getPricing(productId)` | `GET /api/pricing/<product_id>` |
| `getPricingRecommendations(category?, page, pageSize)` | `GET /api/pricing/recommendations` |
| `getPricingExplanation(productId)` | `GET /api/pricing/<product_id>/explanation` |
| `getSegmentExplanation(segmentLabel)` | `GET /api/segments/<segment_label>/explanation` |

---

## Shared components (extracted in Phase 11b)

| Component | Selector | Purpose |
|---|---|---|
| `CategoryChipsComponent` | `app-category-chips` | Column of category filter buttons; emits `select` output |
| `ProductSelectComponent` | `app-product-select` | Search input + scrollable product list; emits `select` and `retry` outputs |
| `ExplanationPanelComponent` | `app-explanation-panel` | Four-state LLM explanation display; pure presentational, no HTTP |

`CategoryChipsComponent` and `ProductSelectComponent` are used by both `ForecastComponent`
and `PricingComponent`. `SegmentsComponent` does not use them (its "chips" filter customers
by segment, not products by category — different data).

---

## Project structure (Phase 11b additions)

```
src/
├── app/
│   ├── core/
│   │   ├── api.service.ts                 Extended: getPricing, getPricingRecommendations,
│   │   │                                  getPricingExplanation, getSegmentExplanation
│   │   ├── models/
│   │   │   └── api.models.ts              Extended: PricingRecommendation, PricingRecommendationsResponse,
│   │   │                                  BindingConstraint, ExplanationResponse, ExplanationSource,
│   │   │                                  ExplanationEntityType
│   │   └── tests/
│   │       ├── api.service.spec.ts        (11a) 10 tests
│   │       └── api-pricing.service.spec.ts (11b) 6 tests
│   ├── shared/
│   │   └── components/
│   │       ├── category-chips.component.ts    (new 11b)
│   │       ├── product-select.component.ts    (new 11b)
│   │       └── explanation-panel.component.ts (new 11b)
│   │   └── tests/
│   │       ├── explanation-panel.spec.ts  (new 11b) 11 tests
│   │       └── ...existing 11a tests
│   └── features/
│       ├── forecast/
│       │   └── forecast.component.*       (modified 11b: uses shared components)
│       └── pricing/
│           ├── pricing.component.*        (new 11b — replaces placeholder)
│           ├── pricing.component.spec.ts  (new 11b) 2 tests (stale guard + timeout)
│           ├── recommendation-card.component.*    (new 11b)
│           ├── recommendation-card.spec.ts        (new 11b) 12 tests
│           ├── recommendations-table.component.*  (new 11b)
│           └── recommendations-table.spec.ts      (new 11b) 12 tests
```

---

## Discrepancies between docs/api.md and real API responses

| # | Field / endpoint | docs/api.md says | Real response | Impact |
|---|---|---|---|---|
| 1 | `recommendation_available: false` | Docs show a minimal-field example with just `no_candidate_reason` and `binding_constraint` | No product in the real data triggers this case — all 50 products return `true` | Interfaces typed to handle both; the `false` branch is tested with mocked data |
| 2 | `/api/forecast/<id>/explanation` | Not mentioned in Phase 10a section | Returns HTTP 200 with `explanation_available: false` and an `unavailable_reason` string | Not a breaking discrepancy; the endpoint exists and is safe to call |
| 3 | P001 explanation text | Docs show full sentence | Real response has `"explanation": "Raise the price for product"` (truncated) | Displayed as-is; this is a real guardrail pass from the LLM, not a backend bug |

---

## Manual verification checklist

After running `npm start` (frontend) and `python app.py` (backend):

| Check | Expected |
|---|---|
| Navigate to /pricing | P001 auto-selected; recommendation card shows current £3.28 and recommended £3.77 |
| Direction tag for P001 | INCREASE (recommended > current) |
| Revenue change tile | Teal background, ↑ arrow, positive amount |
| Bar chart visible | Two bars: Current Revenue vs Expected Revenue |
| Elasticity tile | Shows -0.4676 with helper text |
| Constraints chips | "Min margin: 10.0%" and "Max change: ±15.0%" |
| Explanation panel after rec loads | Yellow block (source badge: llm or fallback), caption present |
| Explanation text is plain text | No HTML rendered even if it contains < or > characters |
| Select P027 | INCREASE tag, negative revenue change with coral/↓, MARGIN binding constraint, CURRENT_PRICE_BREAKS_MARGIN reason code |
| Rapid switching P001→P002→P003 | Only P003 recommendation shows (no P001/P002 flash) |
| Recommendations table | 50 rows loaded, page 1 of 1 |
| Category filter "Electronics" | Table shows ~8 rows; product list filters too |
| Click row in table | Detail card updates to that product; page scrolls up |
| Explanation timeout (simulate by blocking /explanation in browser devtools) | After ~35s panel shows error state with "timed out" and Retry button |
| Stop backend | Health badge turns coral OFFLINE; all panels show error states with Retry |
| Restart backend | Health badge returns teal ONLINE; Retry buttons restore data |
| Forecast and Segments views | Still function identically after shared component extraction |
| No budget warnings in ng build | Confirmed (pricing chunk: 103 kB, under 1 MB error threshold) |

---

## Known limitations

- No URL-based product persistence (`?product=P001` query param). State is in-memory only.
- The `recommendation_available: false` branch cannot be manually verified because no product
  in the real data triggers it. It is covered by mocked unit tests.
- jsdom (Vitest's test environment) prints "Not implemented: HTMLCanvasElement's getContext()"
  warnings during test runs. These are harmless — the chart wrapper catches the error and skips
  chart creation in non-canvas environments.
- Segment explanation (`getSegmentExplanation`) is wired in the API service but is not yet
  displayed in the Segments view. Phase 12 can add explanation cards to that view using the
  same `ExplanationPanelComponent` without any new HTTP plumbing.
