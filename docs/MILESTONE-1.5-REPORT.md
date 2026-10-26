# Milestone 1.5 — premium visual experience

Date: 2026-10-24. Scope: frontend visuals, responsive assets, documentation and frontend verification. The FastAPI contract, SQL schema, migrations and Compose configuration were not changed.

## Visual work

Following the supplied product reference, the desktop homepage now opens with a full-width sunset panorama, soft light-to-art fade, and left-aligned Ubuntu headline and search. The collection strip overlaps the bottom edge of the hero. At phone widths the copy and controls stay on a clear surface and the artwork becomes its own intentional scene below them. Six suggestion chips run through the same search URL encoding and validation as typed input. Navigation retains the responsive menu and theme switch.

A new horizontal collection panel reports only source, truthful collection status and whether observations are waiting. The trending shelf remains a designed empty state when there is no data. Explore now reads as a topic analysis workspace with disabled, legible filters, a clean interest chart empty state and related-topic/comparison placeholders. Trending has room for future measured cards and a transparent ranking-method section. Predictions presents disabled horizons and an explicit no-model state. About tells the data-source story beside the illustration. The shared colors, Ubuntu font and dark theme remain in place.

The reusable TrendCard accepts explicit rank, topic, category, observed post count, growth, optional measured activity points and optional illustration with alt text. It omits metrics it does not receive and does not fabricate a sample series. Unit tests cover empty, populated and invalid-series behavior. No trend card is currently rendered as a real observation.

## Illustration assets

`apps/web/public/images/hero/city-sunset-study-terrace.webp` is derived from the user's 2172 × 724 clean hero illustration. Sharp produced 1920 × 640 at WebP quality 82: 2,337,732 source bytes to 202,488 output bytes (91.3% smaller).

`apps/web/public/images/topics/` has 18 crop-only 352 × 194 WebP scenes derived from the user-provided labelled dashboard sheet. Text and card labels were excluded; crops were visually reviewed together. At quality 80, the files total 348,046 bytes versus 3,111,368 bytes for the original sheet (88.8% smaller). Cards use art only when explicitly supplied alongside a matching real topic. The mockup itself and its metrics are never rendered. See [illustration guidelines](ILLUSTRATION-GUIDELINES.md) for mappings and crop rules.

The product concept screenshot informs hierarchy and tone only; it is not stored or used as a page background. Source artwork was supplied from the user's Downloads directory. The source creator and redistribution terms were not independently verified; confirm rights before public redistribution if needed.

## Files changed or added

- `apps/web/src/app/globals.css` — refreshed responsive tokens, layout, interaction and dark-theme styles.
- `apps/web/src/app/page.tsx` — illustrated hero, live-status panel, trends shelf and discovery paths.
- `apps/web/src/app/{explore,trending,predictions,about}/page.tsx` — shared visual language and truthful analytics states.
- `apps/web/src/components/{search-form,collection-notice}.tsx` — query suggestions and collection panel.
- `apps/web/src/components/trend-card.tsx` — optional artwork and supplied-data-only metrics and sparkline.
- `apps/web/src/components/trend-card.test.tsx` — empty, populated and invalid-series card coverage.
- `apps/web/public/images/hero/` and `apps/web/public/images/topics/` — optimized WebP artwork.
- `tests/e2e/foundation.spec.ts` — source image, suggestion routing, collection empty state and tablet checks.
- `README.md`, `docs/DESIGN-SYSTEM.md`, `docs/IMPLEMENTATION-STATUS.md` and new `docs/ILLUSTRATION-GUIDELINES.md` and this report.

## Performance and accessibility

Local WebP assets remove runtime dependence on remote image hosting. Next `Image` declares viewport-specific `sizes`; the main hero is preloaded and smaller About art remains non-priority. Screenshots are not set as CSS backgrounds. No additional frontend runtime dependency was introduced. CSS transitions remain short and reduced-motion styles are retained. Meaningful scene alt text, named suggestion groups, keyboard controls, focus rings, disabled filter labels and semantic headings are included. Responsive Chromium checks cover horizontal overflow. A formal WCAG 2.2 AA audit, Safari testing and physical-device testing were not performed.

## Verification

| Check | Result |
| --- | --- |
| Frontend lint | Passed — `npm run lint` |
| TypeScript typecheck | Passed — `npm run typecheck` |
| Frontend unit tests | Passed — 10 tests across 3 files (`npm test`) |
| Production build | Passed — `npm run build` with webpack |
| Browser checks (desktop/mobile/tablet) | Passed — 20 Playwright cases across desktop and mobile projects, including tablet viewport checks |
| Backend tests | Not rerun; no backend or database code changed |
| PostgreSQL/Docker runtime | Not part of the visual change; the Milestone 1 Docker access limitation remains recorded in implementation status |

Browser checks used the locally installed Chromium executable and a dedicated development server on port 3100. A separate application already occupied port 3000; no unrelated process or container was changed. Temporary screenshots were captured outside the repository for desktop and mobile visual review.

## Current limitations

There are no collected posts, live trend rankings, working history filters, comparison calculations, forecasts or related-topic recommendations. Filters and forecast horizons stay disabled. Illustration crops are optional visual assets, never evidence of trending activity. Search performs its existing query navigation; it does not run a text-matching engine. Browser emulation does not certify native iOS/Android rendering.
