# TrendSky illustration guidelines

## Visual language

TrendSky's scenes share a contemporary editorial, painterly style: cobalt and deep-blue shadows, luminous skies, warm sunset light, layered city and landscape detail, expressive human silhouettes and small moments of connection around technology. Foliage, terracotta, distant mountains and windows add lived-in context. Keep a coherent light direction and a broad, cinematic sense of place.

People should feel engaged in an everyday moment, not posed as product spokespeople. Devices may appear as environmental details, with screens kept incidental and unreadable at normal display size. Compose expressive faces away from headings, search controls and card text. Leave enough atmospheric detail for useful responsive crops.

## Supplied artwork and crops

The user-supplied **City Sunset Study Terrace.png** is the original hero source: a clean, wide 2172 × 724 editorial scene with no overlaid TrendSky interface or text. The web version, `apps/web/public/images/hero/city-sunset-study-terrace.webp`, is resized to 1920 × 640 and encoded as WebP quality 82 with Sharp. The 2,337,732-byte PNG became a 202,488-byte asset, a 91.3% reduction. The original remains in the user's Downloads directory; it is not duplicated into the repository.

The user-supplied **Trending Life Illustrated Dashboard.png** is a 2172 × 724 contact sheet with baked-in topic labels and dashboard composition. It is never presented whole. Eighteen individual illustration crops in `apps/web/public/images/topics/` retain the clean upper image region and remove embedded category labels and surrounding UI. Each crop is 352 × 194 WebP at quality 80; all 18 total 348,046 bytes. The source PNG is 3,111,368 bytes. Crops were reviewed together for unwanted text, white panel seams and inconsistent appearance.

Optional crop filenames are `caturday`, `gaming`, `climate-change`, `mexico`, `productivity`, `books`, `art`, `technology`, `space-astronomy`, `music`, `sports`, `travel`, `food`, `mental-health`, `science`, `lifestyle`, `entertainment` and `health-wellness`. These describe the artwork subjects only. They do not denote currently trending topics or verified events.

The user-supplied **TrendSky_ Discover What’s Rising.png** reference is a composed product mockup, not a site background or an asset to put beneath HTML. It informs the hierarchy, warm light, spacious search treatment and status strip. Its text, navigation, metrics and cards are not reused.

The source files were provided by the user. Their original creator and redistribution terms were not independently verified. Confirm image rights before public redistribution if the user is not the rights holder.

## Using artwork in the product

- The hero uses Next.js `Image` with an accessible scene description, responsive sizes and an intentional cover crop. At phone widths the image becomes its own landscape scene below the copy; it is not shrunk to a letterbox panorama or used under text.
- Artwork-free TrendCard layout is the default. Illustrations are optional input data, never inferred from post text or an event name. Add an image only when it genuinely describes the measured topic and does not suggest a specific unverified event.
- Each topic image has a category-oriented filename and no embedded label. It does not imply that topic is currently trending. A future card renderer must receive both an explicit source path and meaningful alt text; omit imagery when the match is uncertain.
- Use a consistent crop rather than stretching images. Verify face placement, screen widths, dark-theme presentation and labels after changing the crop or source.
- Keep animation restrained and honour reduced-motion preferences. Do not make artwork essential to understanding activity values or trend rankings.

## Asset workflow

Put original user-provided art outside tracked output until attribution and crop choices are settled. Derive production assets using a scripted, repeatable crop and image encoder. Record source dimensions, crop region, output dimensions, format and compression settings here. Inspect a contact sheet at normal card size. Do not edit the original. Prefer WebP or AVIF when output quality is visually sound and the target framework can deliver it efficiently.
