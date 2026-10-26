# Trend methodology — deterministic-v1

## Question and scope

Which observed public Bluesky conversations have substantial independent participation, growing activity, or newly elevated activity? The baseline hypothesis is that contributor-capped activity plus comparable-window growth provides more useful discovery than raw post volume. This is an interpretable descriptive ranking. No significance, representativeness, causal, forecast, or model-accuracy claim follows from a high score.

## Topic extraction

- Identity is SHA-256 of `kind:normalized_text`. Hashtags, keywords, and phrases have separate identities. There is no fuzzy merge, stemming, or semantic interpretation.
- NFKC Unicode normalization and case folding preserve accents. Repeated mentions of a topic in one post produce one `post_topics` association.
- Hashtags combine existing stored tag relationships (including rich-text facets) and normalized text extraction. Invalid/empty tags are rejected. Up to 32 unique tags are extracted from one post.
- Keywords use Unicode word tokens, URL removal, punctuation separation, minimum length 3, maximum length 40, English/Spanish stopword lists, repeated-character exclusion, and a stable first-occurrence limit of 12 unique keywords per post.
- More than three URLs, or a token representing over 60% of at least ten tokens, suppresses keyword/phrase extraction. Hashtags remain available; contributor caps also limit repetitive posting in ranking.
- The first declared language tag supplies `en`, `es`, `other`, or `unknown`. Absence is never classified as English. Unknown/other posts supply hashtags only. Declared metadata is not language detection and can be inaccurate.
- Phrase extraction uses an explicit configurable lexicon of 2–4 word phrases with whitespace boundaries, such as `climate change` and `cambio climático`. It does not join across sentence punctuation. Frequency/contributor thresholds apply before ranking. This conservative lexicon sacrifices recall to avoid calling arbitrary bigrams meaningful topics.

The same post may count for several distinct topics. Topic counts must not be summed as a count of unique conversation posts. No share-of-conversation metric is exposed in this milestone.

## Event time and boundaries

Activity time is the valid source `created_at`, with Jetstream `event_at` as fallback. A creation time over five minutes beyond its source event is treated as invalid and falls back to `event_at`. Ingestion time remains the operational/retention clock. An update with unchanged creation time preserves activity placement; records missing a valid creation time use their latest source event, which can move placement after an update.

The default publication boundary `T` is UTC now minus 60 seconds, truncated to a whole minute. For `w` in 5, 15, 60, 360, and 1440 minutes:

- Current: `[T-w, T)`.
- Previous: `[T-2w, T-w)`.
- Baseline: six earlier, non-overlapping windows, excluding current and previous.

These are rolling windows with minute-aligned UTC ends. The 24-hour view is not a local-calendar-day bucket. Boundaries are half open; a post at the start is included and a post at the end belongs to a later window.

## Coverage

Successful collection periods are merged, clipped to a window, and known gap intervals are subtracted. Open periods stop at the earliest of the publication boundary, latest heartbeat, and latest source event. Coverage before first collection and before the current retention boundary is unavailable. An unresolved reconnection/cursor gap extends to the next confirmed collection period when that boundary is available.

`observed_minutes` is covered interval duration. A window is `complete_observed_window` only when its entire duration is covered with no overlapping known gap. Earlier windows are `insufficient_history`; other incomplete windows are `partial_coverage`. This describes the collector's observations and does not guarantee complete Bluesky representation. Growth and acceleration require both current and previous windows to be complete. Missing chart samples are null, even when zero matching posts were retained during that incomplete period.

The processor pauses publication when queued changes could affect the publication boundary. Late arrivals invalidate affected snapshots when their activity time precedes a saved boundary. Later cycles recalculate them. Connectivity coverage cannot guarantee that no future late arrival will correct an earlier count.

## Signals

Let `C` and `P` be distinct retained matching posts in current/previous windows, `U` current distinct contributor DIDs, and `w` window duration in minutes. DIDs are used for aggregation and never exposed by trend endpoints.

| Signal | Definition and edge cases |
| --- | --- |
| Current activity | `C`; one association per post/topic |
| Velocity | `C / observed_minutes`; null if no covered minutes. Partial coverage is labelled. Unit: observed posts/minute |
| Growth | `100*(C-P)/P` only with two complete windows and `P>0` |
| New activity | With two complete windows, `P=0,C>0`: null growth and `growth_state=new_activity` |
| No activity | With two complete windows, `P=C=0`: null percentage, `no_activity` |
| Acceleration | `(C-P)/w²` only with comparable windows. Unit: posts/minute² |
| Baseline median | Median of at least three complete baseline windows; otherwise null |
| Baseline MAD | Median absolute distance from baseline median |
| Baseline deviation | `(C-median)/(1.4826*MAD)`; null for zero MAD or insufficient history. A descriptive robust distance, with no p-value interpretation |
| Baseline lift | `(C+1)/(median+1)` when median exists; defined even for a zero baseline |

Counters reflect currently retained records. Source edits, deletes, account/sync purges, and retention can correct earlier activity. This is not an immutable archive of every post ever observed.

## Scores and statuses

Let `K` and `Q` be current and previous activity capped at three matching posts per contributor per window. `V=K/(K+20)`, `A=U/(U+10)`, `G=max(0,(K-Q)/(K+Q+1))` when comparable and zero otherwise, and `B=max(0,(C-median)/(C+median+1))` when a baseline exists and zero otherwise.

`Momentum = 100*(0.25*V + 0.25*A + 0.35*G + 0.15*B)`.

Each component is bounded, so a large raw count cannot dominate by its numerical scale. Momentum is a score from 0 to 100, not a probability or an absolute popularity index.

Defaults: normal minimum `C>=5` and `U>=3`; emerging minimum `C>=10` and `U>=5`; rising/declining threshold 25%; unusual baseline lift 2. All are configurable.

| Status | Deterministic rule, in precedence order |
| --- | --- |
| Emerging | Normal and emerging sample minima, comparable windows, capped activity increases, and either new activity (`P=0`) or growth at least 25% with baseline lift at least 2 |
| Rising | Normal minima, comparable windows, capped activity increases, and growth at least 25% |
| Declining | Comparable windows and growth at most -25%. A formerly substantial topic with at least 5 previous posts and 3 previous contributors may decline below current minima, including to zero |
| Stable | Normal current minima, comparable windows, and growth strictly between -25% and +25% |
| Insufficient Data | Every remaining case, including incomplete coverage or raw growth unsupported by capped participation |

## Ranking concepts

- **Popular Now:** `ln(1+K)*ln(1+U)`, with normal sample minima. Partial current coverage can be shown as observed activity; unavailable comparisons remain null.
- **Rising Fast:** `Momentum*G`, eligible only for Rising/Emerging conditions with normal minima and positive capped growth.
- **Emerging:** `Momentum*max(G,B)`, eligible only for Emerging conditions.

Categories can overlap; Emerging topics can also be Rising Fast. Stable ordering is score descending, current posts descending, contributors descending, topic ID ascending. A single-author topic cannot qualify. Several coordinated accounts can still manipulate this descriptive baseline; the system does not identify bots or prove authentic participation.

For bounded work, each window considers up to 500 topics (configurable) with at least 5 posts and 3 contributors across current plus previous windows, selected by contributor count, then volume, then ID. This cap is disclosed by the engine status endpoint. Phrase frequency thresholds use the same sample minima. Rare topics can be discovered/searchable without qualifying for rankings.

## Corrections, freshness and validation

Source database triggers coalesce work by post URI, invalidate affected historical snapshots and remove obsolete associations inside the source transaction. The independent worker replaces per-post associations atomically, then computes SQL snapshots. Source revisions are captured before calculation and rechecked under short, non-blocking topic locks before publication. New observations after a saved boundary do not erase that valid earlier snapshot.

Rankings older than 180 seconds are excluded from discovery. Topic detail can return an explicitly stale historical calculation with growth suppressed. The test suite and [synthetic evidence](evidence/milestone-3-synthetic.json) cover stable, rising, declining, emerging, single-author, gap and deletion scenarios. The evidence dataset is synthetic and has no professional performance or business-outcome implication.
