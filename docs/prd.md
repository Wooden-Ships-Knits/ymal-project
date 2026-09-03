# YMAL — Product Requirements

**Project:** In-house "You May Also Like" recommendations
**Store:** Wooden Ships (`wooden-ships.myshopify.com`)
**Status:** Draft — pending discussion
**Last updated:** 2026-09-03

---

## 1. Background

The Wooden Ships storefront currently shows product recommendations ("You May
Also Like") powered by **Wiser AI**, a third-party Shopify app.

It works, but it is a black box:

- We cannot see why a product was recommended.
- We cannot encode our own product knowledge — that a cardigan pairs with a
  particular dress, that two items belong to the same drop, that a style is
  being pushed this month.
- We cannot stop it recommending things we don't want recommended (out-of-stock
  styles, four colorways of the same sweater, off-season items).
- We cannot easily measure its contribution or compare it to an alternative.
- Any change we want depends on the vendor's roadmap, not ours.

The team already runs Shopify data pipelines in Python (`Collection VO
Automatic Sort`, `Price_Book_Automation`, `judgeme-review`, and others), so the
capability to build this in-house exists and the patterns are established.

---

## 2. Problem statement

We do not control the recommendation logic on our own product pages, and we
cannot tune it with knowledge we already have about our own catalog.

---

## 3. Goals

**Primary**
1. **Own the logic.** Recommendations are produced by rules and signals we can
   read, change, and explain.
2. **Merchandiser control.** The web admin team can pin, block, and override
   recommendations without engineering involvement.
3. **Match or beat Wiser** on the agreed success metric before we switch off.

**Secondary**
4. Remove the dependency on (and cost of) a third-party app.
5. Build a foundation reusable for other placements — cart, collection,
   homepage, email.

---

## 4. Non-goals (explicitly out of scope for v1)

- Replacing Shopify's native search.
- Personalized recommendations for logged-out visitors.
- A machine-learning model with embeddings or a training pipeline. If simple
  co-occurrence plus attribute matching isn't enough, that's a v2 decision made
  with evidence.
- Recommendations in email or paid channels.
- A general-purpose product usable by other stores.

---

## 5. Success metrics

> **Needs agreement before build starts.** We cannot claim an improvement
> without a number defined up front, and we cannot measure the baseline after
> Wiser is uninstalled.

| Metric | Baseline (Wiser) | Target |
|---|---|---|
| Widget CTR | TBD — must capture | ≥ baseline |
| Attributed revenue / session | TBD | ≥ baseline |
| AOV, sessions engaging widget | TBD | ≥ baseline |
| Catalog coverage (products with recs) | TBD | ~100% of active products |
| Empty-widget rate | TBD | ~0% |

**Time-sensitive:** capturing Wiser's current recommendations and performance
is only possible while Wiser is still live. This should happen early.

---

## 6. Users

| User | Need |
|---|---|
| **Shopper** | Relevant, in-stock, appealing suggestions; fast page load |
| **Web admin / merchandiser** | See what's recommended, override it, without code |
| **Us (engineering)** | Debuggable pipeline, explainable output, safe rollout |

---

## 7. Requirements

### Must have (v1)
- Recommendations for every active, purchasable product.
- Product-page placement, replacing the Wiser widget position.
- Never show: the anchor product itself, out-of-stock items, draft/archived
  products.
- Colorway dedupe — no showing the same style repeatedly in different colors.
- Merchandiser pin/block override.
- Impression and click tracking, for measurement.
- A fallback chain so the widget is never empty.
- A kill switch to restore Wiser without a deploy.

### Should have
- Price-band sanity rules.
- Diversity rules (mixed product types within one set).
- A per-run report: coverage, churn vs previous run, failures.

### Could have (later)
- Cart and collection placements.
- Personalization from customer purchase history.
- Browsing/view signals via a Shopify Web Pixel.

### Won't have (v1)
- Real-time per-session recommendations.
- Any change requiring a new hosted service, unless the serving decision in
  `backend.md` §4 goes that way.

---

## 8. What to do — phases

**Phase 0 — Groundwork**
- Confirm API scopes (esp. `write_products` for metafields).
- Capture Wiser's current recommendations + performance as the baseline.
- Audit product tag quality — the content-similarity signal depends on it.
- Decide the serving model (`backend.md` §4).

**Phase 1 — Data**
- Extract products, orders, inventory from the Admin API.
- Build the per-product feature table.

**Phase 2 — Logic**
- Fill in `logic.md`, then implement the scoring and rules.
- Evaluate offline against held-out order history.

**Phase 3 — Publish**
- Write recommendations to their destination.
- Per-run reporting and monitoring.

**Phase 4 — Frontend**
- Theme snippet, backed up and previewed before publishing.
- Impression/click tracking.

**Phase 5 — Prove it**
- Run alongside Wiser, split traffic, compare on the agreed metric.
- Only then decide whether to remove Wiser.

---

## 9. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Poor tag data undermines content similarity | High | Audit in Phase 0, before relying on it |
| No baseline captured before Wiser is removed | High | Capture in Phase 0; keep Wiser installed |
| Cold start — new products get bad recs | Medium | Content-based fallback when history is thin |
| Metafield write limits / API throttling | Medium | Bulk mutations, batching, backoff |
| Theme change breaks the storefront | High | Backup + preview + kill switch |
| Recs go stale between nightly runs | Medium | Re-check availability at render time |
| Project stalls after Wiser is cancelled | High | Do not cancel Wiser until Phase 5 passes |

---

## 10. Open questions

1. Serving model: precompute to metafields, or live API?
2. Do we need view/browsing data, or are orders enough for v1?
3. What is the agreed success metric and its baseline?
4. How much order history is available and usable?
5. Where do merchandiser overrides live — Google Sheet or Shopify metafields?
6. How many recommendation slots does the widget have?
7. Is there a deadline, or a Wiser contract renewal date driving timing?
