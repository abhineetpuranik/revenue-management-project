# Phase 11a — Angular Dashboard

## Deliverables

Phase 11a implements the Angular 21 dashboard frontend covering Phase 10a API endpoints (forecast, segments). Phase 10b endpoints (pricing, explanations) are scaffolded as a placeholder for Phase 11b.

---

## Build & test results

| Step | Result |
|---|---|
| `ng build --configuration development` | ✅ 0 errors, 0 warnings |
| `ng test` | ✅ 34 tests pass, 0 failures |
| Bundle sizes (lazy) | forecast: 52 kB, segments: 50 kB, pricing-placeholder: 10 kB |

---

## Architecture decisions

**Standalone components everywhere.** Angular 21 has removed NgModules from the default scaffold. All components use `standalone: true` and declare their own `imports[]`.

**Signals for state management.** `signal()`, `computed()`, and `effect()` from Angular 21's reactivity system replace `BehaviorSubject`/`async` pipe patterns. This keeps state reads explicit and avoids subscribe-in-subscribe patterns.

**`takeUntilDestroyed(destroyRef)` for HTTP subscriptions.** Injected `DestroyRef` is used with the RxJS interop operator so HTTP subscriptions are cancelled when a component is destroyed — no manual `ngOnDestroy` unsubscribe needed (except in `HeaderComponent` which uses `interval()`).

**Chart.js registered once.** `ChartWrapperComponent` registers all required Chart.js components on first import. The tree-shakeable registry means only used chart types are bundled.

**Lazy-loaded routes.** All three feature components are lazy-loaded via `loadComponent()`. The router only fetches the chunk when the user navigates to that route.

**CSS custom properties for theming.** All design tokens live in `src/styles/tokens.scss` as `:root {}` CSS variables. Component styles reference them via `var(--token)`. This makes the design system easily overridable without touching component code.

**Font loading via angular.json styles[] array.** Fontsource CSS files cannot be loaded with Sass `@use` (they're plain CSS). They are listed in `angular.json` → `architect.build.options.styles` before `src/styles.scss`.

---

## API usage

All HTTP calls go through `ApiService` (`src/app/core/api.service.ts`). Components never touch `HttpClient` directly. Error handling normalises all errors to a `DisplayError { status: number; message: string }` shape:

- `status: 0` = network/connection error
- `status: 404` = resource not found (API format: `{ error: { status, message } }`)
- `status: 400` = bad request (pagination params)

---

## Verification checklist (manual)

After running `npm start` and `python app.py`:

| Check | Expected |
|---|---|
| Header health badge on load | Shows TEAL "ONLINE" within ~1s |
| Navigate to /forecast | Product list loads, P001 auto-selected |
| Forecast chart | History bars in lime, test window in teal, purple dashed predicted line |
| Category chip "Electronics" | Product list filters to Electronics products |
| Model comparison table | XGBoost row shows "✓ Selected" badge |
| Navigate to /segments | 4 stat tiles, doughnut chart, segment table visible |
| Segment filter "High Value" | Customer table shows only high_value customers |
| Customer lookup "C0001" | Shows segment_label, recency, frequency, monetary |
| Customer lookup "ZZZZ" | Shows error state (404) — no crash |
| Navigate to /pricing | Placeholder stat tiles + feature list |
| Stop backend, wait 30s | Health badge turns CORAL "OFFLINE" |
| Restart backend | Health badge turns TEAL "ONLINE" again |

---

## Known limitations

- No skeleton loading screens — `app-loading-state` uses a CSS spinner.
- No URL-based product selection (no `?product=P001` query param). Navigation state is in-memory only.
- Forecast chart does not annotate the train/test boundary with a vertical line — the colour change on data points conveys this instead.
- Segment doughnut shows **revenue share** (not customer share) because that was more informative. Customer share is shown in the stat tiles.
