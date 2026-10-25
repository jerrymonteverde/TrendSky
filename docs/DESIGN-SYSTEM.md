# Design system

The mandatory [Blue Sky palette](https://www.color-hex.com/color-palette/14256) is stored as CSS custom properties in `apps/web/src/app/globals.css`.

| Token | Value | Use |
| --- | --- | --- |
| Brand primary | #2D5D83 | Brand, light-mode controls, links |
| Brand secondary | #4F9BD9 | Brand emphasis, selection, future series |
| Brand accent | #25C5DF | Small decorative highlights, dark-mode focus |
| Brand neutral | #8B888E | Non-text muted marks |
| Brand background | #FFFFFF | Light surface |

Derived text colours (#60717E on white; #A7B8C5 on #111D27) keep small copy readable. Cyan is not used for small white-background text. Primary buttons use white on #2D5D83; dark controls use dark text on #4F9BD9. Visible focus, labelled controls, skip navigation, reduced-motion support and disabled states are part of the foundation. Browser tests check overflow at desktop and mobile widths; no formal WCAG audit is claimed.

[Ubuntu](https://design.ubuntu.com/font), normal style, weight 400, is the principal font. Weight 500 is used sparingly for small hierarchy labels. Unmodified Latin WOFF2 subsets include Spanish accents and are bundled with their licence. `next/font/local` preloads and optimizes them without external runtime requests. Fallbacks are Arial and sans-serif. Theme preference uses `next-themes` local storage, defaults to light, and persists on reload.

Local UI primitives follow shadcn/ui's owned-component approach (`components.json`, CVA variants, Radix Slot and `cn`). Chart colours and series patterns are deliberately deferred to the chart milestone; there is no chart implementation to certify yet.
