# YMAL — Caveats

Things that could bite us. Assumptions not yet validated, platform limits,
data-quality risks.

---

## 0. Validation plan — the Google Sheet

**Agreed 2026-09-03.** A hand-built Sheet of eligible ("unfix") products, keyed
on `product_id`, serves as the **answer key** for everything in §1.

The method: derive eligibility from the API (Bali location + no `*SALE*`), diff
against the Sheet, and read the result.

| Outcome | Meaning |
|---|---|
| Lists match | Rule validated — automate it, close §1 and §5 |
| API list is **larger** | Rule is too permissive — something ineligible is leaking through |
| API list is **smaller** | Rule is too strict — likely a location-name or marker-variant miss |
| Rows disagree individually | Each mismatch names a specific broken assumption |

This is the cheapest way to resolve the §1 questions. Most of them stop being
guesses the moment we have both lists side by side.

**Caveat on the caveat:** the Sheet is a snapshot. It is ground truth on the day
it is built and drifts from that moment on. It validates the rule; it must not
become the permanent source of truth. See `memory.md` decisions #7 and #9.

---

## 1. The fixed / SALE eligibility rule

The rule is recorded in `logic.md` §4.1. It was written from a verbal
description and **has not been checked against real catalog data**. The Sheet
diff in §0 is how most of these get answered — but they are listed explicitly
because each one can silently produce a wrong catalog split.

### Location / "unfix"

- What is the **exact** location name in Shopify? `"Bali"`, or something longer
  like `"Bali Warehouse"` / `"Bali Production"`? An exact-string match on the
  wrong name silently excludes everything.
- Are there **other** production locations besides Bali? If a second one exists,
  the rule as written wrongly excludes it.
- What if a product has inventory at **multiple** locations, Bali *and* a
  fixed-stock warehouse? Does Bali presence make it eligible, or does any
  fixed-stock location disqualify it?
- Is location the real signal for "replenishable", or is it a proxy that
  happens to correlate today? A proxy that drifts is a rule that quietly rots.
- Products with **zero** inventory at Bali but assigned to it — eligible or not?

### `*SALE*` in the title

**Resolved 2026-09-03:** the marker is asterisk-delimited — `*SALE*`, not the
bare word. Matching the full token removes the substring false-positive risk
(`WHOLESALE`, `Salem`) that a bare-word match would have carried.

Still to verify:

- **Case** — is it always uppercase `*SALE*`, or do `*Sale*` / `*sale*` appear?
- **Spacing** — any `* SALE *` or `*SALE *` variants in the wild?
- **Extended forms** — does `*SALE 50%*` or `*FINAL SALE*` occur? If so, match
  on `*SALE` opening rather than the exact closed token.
- **Malformed markers** — a missing closing asterisk (`*SALE`) would evade an
  exact-token match and leak a markdown item into the widget.
- **Position** — always prefix, always suffix, or either? Affects nothing if we
  use containment, but worth knowing the convention.
- Is the title the **only** marker for sale items, or is there also a tag,
  collection, or `compare_at_price`? A structured field would be more reliable
  than a human-edited string, and could serve as a cross-check.
- Who edits titles, and how consistently? A forgotten marker is a silent leak.

**Recommended verification:** count active products whose title contains
`*SALE*`, then cross-check that count against products with a sale tag or a
`compare_at_price` set. A large mismatch means the title marker is not applied
consistently and should not be the sole signal.

### Scope of the rule

- Does this filter apply to the **recommendations only**, or also to the
  **anchor** — i.e. should a SALE product page show a YMAL widget at all?
- Does it apply to every placement (product page, cart, collection), or only
  the product page?

---

## 2. Catalog-size risk ⚠️

This is the one most likely to cause real trouble.

The rule excludes fixed-stock **and** SALE products. Depending on the split,
that could remove a large share of the catalog from the eligible pool.

The knock-on effects:

- The 30-deep candidate pool (`memory.md` decision #4) may not be reachable for
  many products.
- Thin or empty widgets — the exact failure the fallback chain exists to
  prevent, but the fallback pool is drawn from the same shrunken set.
- Recommendation quality drops as the pool narrows; diversity rules get harder
  to satisfy.

**Cannot be assessed without counting.** The Sheet (§0) answers this directly
and immediately — its row count *is* the eligible catalog size.

Rough read on what the number means:

| Eligible products | Implication |
|---|---|
| Comfortably > 1,000 | 30-deep pool is fine, proceed as planned |
| A few hundred | Pool depth may need reducing; watch diversity rules |
| Under ~100 | Rethink. Pool, slot count, and fallback chain all need revisiting — and cross-category recommendations may be the only way to fill slots |

Take this measurement **before** committing to pool depth or slot count.
Both `memory.md` decision #4 (30-deep pool) and the 6-slot widget assumption
are provisional until this number exists.

---

## 3. Platform limits

- **`read_all_orders` gate** — without approval, order history is capped at
  **60 days**. Not enough for a seasonal catalog. Longest-lead blocker.
- **Admin GraphQL is cost-based**, not request-count based. Watch
  `extensions.cost.throttleStatus` and back off.
- **`metafieldsSet`** writes max 25 per call — batch accordingly.
- **Bulk operations are async** — poll, then download JSONL.
- **Scope changes force re-authorization** of the app on the store.
- **API version pinned** to `2026-01`; a Shopify release should not silently
  change behavior underneath us.

---

## 4. Operational

- **No baseline yet.** Wiser's current output and performance must be captured
  while it is still installed. Once uninstalled, the comparison is gone
  permanently.
- **Tag quality is unaudited** — content similarity depends on it entirely.
- **Live storefront.** Theme changes need backup, preview, and a kill switch.
- **App Proxy backend is a new uptime dependency** on the storefront. The
  metafield fallback path exists so the widget degrades rather than vanishes.
- **Google Drive shared drive** — concurrent access and large artifacts.

---

## 5. Data assumptions to verify

| Assumption | Status | Resolved by |
|---|---|---|
| Bali location identifies replenishable stock | ❓ unverified | Sheet diff (§0) |
| `*SALE*` in title identifies markdown items | ❓ marker format confirmed, coverage not | Sheet diff (§0) |
| Enough eligible products remain for a 30-deep pool | ❓ **unmeasured** | Sheet row count (§2) |
| Order history goes back far enough to be useful | ❓ blocked | `read_all_orders` approval |
| Product tags are consistent enough for similarity | ❓ unaudited | Separate tag audit |

Three of the five clear the moment the Sheet exists. The order-history question
is on Shopify's timeline, not ours — which is why the approval request should
go in first, not last.

---

## 6. Similarity criteria — what makes two products "related"

**Agreed 2026-09-08 with the web team.** Recorded here so the criteria can be
changed later without re-deriving why they were chosen.

All four facets count, weighted. The weights live in
`backend/ymal/settings.py` as `SIMILARITY_WEIGHTS` and can be retuned without
touching the scoring code.

| Facet | Weight | Source |
|---|---|---|
| Motif / pattern | 3.0 | tags: graphic, stripe, football, word, solid, inset, fair isle |
| Fabric / weight | 2.0 | tags: cotton, wool, chunky, lightweight, blend |
| Colour family | 1.5 | tags: neutral, dark, white, black, grassy |
| Silhouette | 1.5 | `product_type_normalised`, not tags |
| Collection | 1.5 | Shopify collections - game-day, beach-lake, cardigans |

**Collections added 2026-09-10.** They are the merchandiser's own grouping, so
two products sharing one were deliberately put together by someone who knows
the range.

Collections on more than 60% of the catalog are dropped before scoring. This
shop has 23 collections and six of them (`testimonial`,
`cloud-search-all-products`, `tax-clothing`, `discount-applicable-*`) sit on
88-100% of products; left in, they would dominate every comparison and make any
two products look related. IDF alone does not neutralise them - its `+1.0`
floor leaves a universal collection at 0.82 against 1.92 for a rare one.

Motif is weighted highest because it is the most visible thing a shopper
matches on. Rarer tags count for more than common ones (IDF), so `football`
(18% of the catalog) says far more about similarity than `cotton-vo` (54%).

**Season is a hard filter, not a score.** A recommendation must be in the same
season as the anchor. This halves the candidate pool — 152 autumn, 102 spring —
so revisit it if pools ever come out thin. Set `REQUIRE_SAME_SEASON = False` to
lift it.

The 4 products with no season tag ignore the rule rather than ship an empty
pool (`SEASONLESS_IGNORES_SEASON`).

### What is deliberately NOT a signal

- **Price.** Measured 2026-09-08: every eligible product is $137-$159, a 16%
  spread clustered on a handful of values. Price cannot distinguish anything on
  this catalog. Revisit if the range ever widens.
- **Sales velocity as a similarity signal.** Folding popularity into similarity
  would make every pool converge on the same bestsellers.

  **Revised 2026-09-10:** popularity now REORDERS a pool without deciding who
  is in it, the same split co-purchase uses - `POPULARITY_WEIGHT = 0.4`, so the
  best seller in a pool can rise by 40%. Measured after the change: the pools
  still draw on 224 of 257 products, and the most-used product appears in 34 of
  257 top-sixes. Convergence did not happen, but it is the thing to re-measure
  if the weight is ever raised.

### To change the criteria

1. Edit `SIMILARITY_FACETS` or `SIMILARITY_WEIGHTS` in `backend/ymal/settings.py`
2. `cd backend && python -m scripts.build_pools --show "SOME PRODUCT TITLE"`
3. Read the pool and decide whether it looks better

Nothing is published to Shopify by that script, so retuning is free.

