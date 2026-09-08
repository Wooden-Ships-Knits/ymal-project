# YMAL — Recommendation Logic

> **Status: empty on purpose.** To be filled during the logic discussion.
>
> This document should end up describing *how a recommendation is actually
> decided* — what signals feed in, how they're combined, and what rules
> override them. It is the part that differentiates us from Wiser, so it
> deserves its own conversation rather than a first-draft guess.

---

## 1. Signals

_What data do we use to decide two products are related?_

**Content signals (Phase 3, built 2026-09-08).** Four facets, from the Phase 2
feature table: motif/pattern, fabric/weight, colour family, and silhouette.
Season is a hard filter rather than a signal.

Price is deliberately excluded - the catalog spans $137-$159, so it
distinguishes nothing. See `caveats.md` section 6.

**Collaborative signal (Phase 4, built 2026-09-08).** Co-purchase from a year
of orders, counted at style level and scored by lift rather than raw counts -
bestsellers appear in every basket, so raw co-occurrence would just rediscover
the top sellers.

---

## 2. Scoring

_How each signal produces a score._

Each tag-based facet scores as an IDF-weighted Jaccard overlap between the
anchor's tags and the candidate's, within that facet. Rarer tags count for
more, so `football` says more about similarity than `cotton`.

Silhouette is binary: same normalised product type or not.

Implemented in `backend/ymal/similarity.py`, weights in `settings.py`.

---

## 3. Blending

_How multiple signals combine into one ranked list._

A weighted sum of the four facet scores. The total is comparable within one
anchor's pool, which is all ranking needs - it is not a probability.

Then the hard rules: same season, never the anchor's own style, one product per
`style_key`, and eligible products only. Top 30 are stored.

Co-purchase **reranks only** - it reorders the 30 without changing who is in
them, so a co-purchase pair can never break the rules above. A candidate with
no co-purchase history keeps its content order, which is the cold-start path
and the permanent one for a product launched today.

---

## 4. Business rules

_Hard filters and merchandising overrides applied on top of the scores._

### 4.1 Eligibility rule — fixed stock and SALE (notes, 2026-09-03)

**Requirement, as stated:** products that sell fixed stock, and products on
sale, must **never** appear in the recommendation widget.

**Why it matters:** recommending a fixed-stock item drives demand at something
we cannot restock — the shopper hits an unavailable product, or we burn through
finite inventory we were holding. Recommending SALE items pushes traffic to
markdown when the widget's job is to sell at full price.

**How a product is identified as eligible ("unfix"):**

Both conditions must hold.

| # | Condition | Source |
|---|---|---|
| 1 | Stock is replenishable — produced at the **Bali** location | Inventory location |
| 2 | Title does **not** contain the marker **`*SALE*`** | Product title |

Fails either → excluded from the candidate pool.

**On the `*SALE*` marker (updated 2026-09-03):** the sale marker written into
product titles is asterisk-delimited — literally `*SALE*`, not the bare word.
Match on the full delimited token, not on `SALE` alone. This removes the
substring false-positive risk (`WHOLESALE` and similar) that a bare-word match
would have.

Implementation note for later: `*` is a regex metacharacter. Use literal string
containment, or escape it (`\*SALE\*`). An unescaped `*SALE*` in a regex means
something entirely different and will not match what we want.

**Where this runs:** serve time, not batch. Location/stock state and title can
change during the day, and this is precisely the staleness that Wiser gets
wrong (see `flow.md` §1). Checking it nightly and trusting it at render would
reproduce the bug we are trying to fix.

**Starting point:** enumerate currently active product pages and read their
location status, to see how the catalog actually splits. Not built yet — this
is the first thing to look at, but no pipeline until the questions in
`caveats.md` §1 are answered.

**Open questions — see `caveats.md` §1.** The rule above is written from a
verbal description and has not been validated against real catalog data.

---

## 5. Fallbacks

_What we show when the primary logic returns nothing._

TBD

---

## 6. Evaluation

_How we know the logic is good, and how we compare against Wiser._

**Offline (Phase 4).** Hold out the most recent 10% of baskets, learn
co-purchase from the rest, and measure hit rate at k=6 - the widget slot count.
Held out by recency rather than at random, because the real task is predicting
what will be bought together next from what was bought before; a random split
leaks the future into the training set.

Measured 2026-09-08 on 12,023 multi-item orders:

| Ranking | Hit rate at 6 |
|---|---|
| Content only | 0.1651 |
| Content + co-purchase | **0.2944** |

Reranking beats content alone by 78% relative, so Phase 4's exit criterion is
met. `scripts/build_copurchase.py` re-runs this and refuses to endorse the
result if it ever stops beating content alone.

**Online (Phase 7).** The A/B test against Wiser. A holdout is the only honest
profit number - see the drawio page 7.
