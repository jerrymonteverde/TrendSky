# Design system

The Milestone 1.5 site adds a warm editorial layout around the existing palette: a full-width panoramic hero with a soft light fade behind the headline and search, a collection panel overlapping the artwork edge, roomy topic discovery surfaces and quiet cards with selective elevation. On phones, the hero art becomes its own scene below the copy. The layout follows the supplied reference's hierarchy without rendering its baked-in UI or implying uncollected data. Shared styles and dark variants remain in `apps/web/src/app/globals.css`.

The selected [blues palette 189](https://www.color-hex.com/color-palette/189) is stored as CSS custom properties in `apps/web/src/app/globals.css`. Deep blue is reserved for readable actions and text; lighter blues are used for emphasis and surfaces.

| Token | Value | Use |
| --- | --- | --- |
| Brand primary | #3366FF | Brand, primary light-mode controls |
| Brand secondary | #5588FF | Brand emphasis, selection, chart series |
| Brand accent | #77AAFF | Highlights and dark-mode controls |
| Palette light | #99CCFF | Dark-mode links and accents |
| Palette ice | #BBEEFF | Icon highlights and soft blue treatments |
| Brand background | #FFFFFF | Light surface |

Derived dark navy text, borders, and muted tones preserve readable contrast on light surfaces. The brighter palette blues are reserved for accents when contrast is insufficient for small text. Primary buttons use white on #3366FF; dark controls use dark navy text on #77AAFF. Visible focus, labelled controls, skip navigation, reduced-motion support and disabled states are part of the foundation. Browser tests check overflow at desktop and mobile widths; no formal WCAG audit is claimed.

[Ubuntu](https://design.ubuntu.com/font), normal style, weight 400, is the principal font. Weight 500 is used sparingly for small hierarchy labels. Unmodified Latin WOFF2 subsets include Spanish accents and are bundled with their licence. `next/font/local` preloads and optimizes them without external runtime requests. Fallbacks are Arial and sans-serif. Theme preference uses `next-themes` local storage, defaults to light, and persists on reload.

Local UI primitives follow shadcn/ui's owned-component approach (`components.json`, CVA variants, Radix Slot and `cn`). Reusable trend cards accept optional measured counts, growth and an observed activity series; the same card works with artwork omitted. The page never instantiates illustrative demo values as live trends.

The hero scene and eighteen optional topic crops are optimized local WebP assets under `apps/web/public/images/`. See [Illustration guidelines](ILLUSTRATION-GUIDELINES.md) for sources, crop safety, asset weight and usage rules. The full mockup image is deliberately not rendered underneath controls.

Explore and Predictions use broad, calm analytical surfaces, clear empty states, soft separators and labelled actions. The mobile navigation preserves reachable link targets and touch-sized controls. Focus rings, disabled filter labels, useful alt text and a low-motion preference are preserved. The trend sparkline is a compact SVG built only from an explicitly supplied series; it is not displayed without at least two valid observations. Browser verification checks desktop and mobile viewport widths, image loading, navigation, suggested-search routing and collection-empty state. No full WCAG audit is claimed.
