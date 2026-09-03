# YMAL — End-to-End Flow

**Revised 2026-09-03** after confirming App Proxy availability and identifying
Wiser's failure mode (stale fixed/sale state at render time).

---

## 1. The governing idea: two stages, different clocks

Wiser's observed failure — showing items whose sale/fixed status is wrong — is
not a *model* failure. It's a **timing** failure. Relevance was computed at some
earlier point, and the item's price/stock/sale state changed before the shopper
saw it.

So we split the system by how fast the data changes:

| Stage | Question | Clock | Where |
|---|---|---|---|
| **Relevance** | Which products are *related* to this one? | Slow — nightly | Offline batch (ML lives here) |
| **Eligibility** | Which of those may we *show right now*? | Fast — per request | Serve time (rules live here) |

Relatedness between two sweaters does not change hourly. Whether one is in
stock, on markdown, or published does. Computing both on the same clock is the
mistake.

**Consequence:** the offline stage stores a **deep pool** (~30 candidates per
product), not the 6 we display. Serve time filters that pool down. A shallow
pool starves the widget as soon as filters bite.

---

## 2. Full picture

```
┌──────────────────────────────────────────────────────────────┐
│ SOURCES (Shopify Admin GraphQL, 2026-01)                     │
│   Products · Orders · Inventory · Publications               │
│   Web Pixel events (views, ATC) — once tracking ships        │
└──────────────────────────┬───────────────────────────────────┘
                           │  nightly (delta; full weekly)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ EXTRACT   → raw snapshots on disk                            │
│   orders via Bulk Operations (needs read_all_orders)         │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ FEATURES  one row per product                                │
│   style_id · colorway · type · tags · price band · season    │
│   collection membership · launch date · sales velocity       │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ RELEVANCE  (ML — see logic.md)                               │
│   collaborative signal  ─┐                                   │
│   content embeddings    ─┼─→ blend → ranked candidate pool   │
│   image embeddings      ─┤     (top ~30 per product)         │
│   complete-the-look     ─┘                                   │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ PUBLISH   pool → metafield  ymal.candidates                  │
│           (product IDs + scores, ~30 deep)                   │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
        ═══════ boundary: everything above is nightly ═══════
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ ELIGIBILITY  ← per request, on live state                    │
│   ✗ out of stock          ✗ unpublished / draft              │
│   ✗ sale/fixed rule       ✗ merchandiser block               │
│   ✗ same style (colorway dedupe)   ✗ price band              │
│   ✓ merchandiser pin (forced to front)                       │
│   → diversity pass → top 6                                   │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ RENDER    theme app extension / snippet → product cards      │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ TRACK     impression · click · add-to-cart                   │
│   → measurement AND training data for learning-to-rank       │
└──────────────────────────┴───────────────────────────────────┘
                           │
                           └──────► feeds back into RELEVANCE
```

---

## 3. Where eligibility runs — two options

The rules must run on live state. Two ways to achieve that:

### 3a. Liquid-side filtering (no backend)

Theme reads the 30-deep pool from the metafield and filters in Liquid:

```liquid
{%- for item in candidates -%}
  {%- if item.available and item.published_at -%}
    ...render, break at 6
```

- ✅ No hosting, no latency, no uptime risk, works with JS off
- ✅ Stock/price/publication are *always* current — Liquid reads live objects
- ❌ Complex rules (diversity, price bands, style dedupe) are painful in Liquid
- ❌ No personalization

### 3b. App Proxy + backend service ⭐ recommended

`wooden-ships.com/apps/ymal?product=…` proxies to our service. Full rule engine
in Python, on live data, same-origin so no CORS.

- ✅ Arbitrary rule complexity — this is where the flexibility you want lives
- ✅ Personalization possible later
- ✅ Rules change without touching the theme
- ❌ Needs hosting + uptime + monitoring
- ❌ Adds latency to the widget

**Recommended: 3b, with 3a as the fallback path.** If the proxy fails or times
out, the theme renders from the metafield pool with basic Liquid filtering.
The widget degrades instead of disappearing, and the storefront never depends
on our uptime being perfect.

---

## 4. Batch flow (nightly)

```
02:00  extract products, orders (delta), inventory, publications
02:15  rebuild feature table
02:30  recompute collaborative signal
02:45  refresh content / image embeddings for new + changed products
03:00  blend → candidate pool (top 30 each)
03:15  publish pools → metafields (metafieldsSet, batched 25)
03:30  run report: coverage, pool depth, churn vs yesterday, API cost used
```

**Coverage and pool depth are the health metrics.** A product whose pool drops
below ~10 will render a thin widget once filters apply.

---

## 5. Request flow (per pageview)

```
shopper opens /products/emily-crew
  → theme app extension renders container + calls /apps/ymal
  → service loads the 30-deep pool
  → applies eligibility rules against live Shopify state
  → diversity pass → top 6
  → returns JSON → cards render
  → IntersectionObserver fires impression event
```

Target: under ~200ms. Cache the pool in memory; the live-state check is the
only part that must be fresh.

---

## 6. Tracking — moved earlier, and here's why

Previously slotted late, as measurement. It is actually **training data**.

Learning-to-rank — the ML that genuinely beats hand-tuned blending — needs
click and conversion data keyed to what was shown. We cannot collect that
retroactively. Every week tracking isn't live is a week of training data lost.

**Tracking ships with the first widget, not after it.**

| Event | Fired when | Payload |
|---|---|---|
| `ymal_impression` | widget enters viewport | anchor, shown ids, positions |
| `ymal_click` | card clicked | anchor, clicked id, position |
| `ymal_atc` | ATC on a recommended product | anchor, product id |

---

## 7. Fallback chain

Never render an empty widget:

1. Personalized (later — needs `read_customers` + session)
2. Collaborative (co-purchase)
3. Content / image similarity
4. Same collection, best-selling
5. Store-wide best sellers

Each level fills remaining slots until 6.

---

## 8. Resolved / still open

**Resolved this session:**
- Serving model → App Proxy backend, metafield pool as fallback (§3b)
- Rules run at serve time, not batch time (§1)
- Tracking ships in phase 1, not last (§6)

**Still open:**
- The exact fixed/sale rule — see `caveats.md` / discussion
- Do we need Web Pixel view data, or are orders + tracking enough?
- Where do merchandiser pins/blocks live — Sheet, metafield, or metaobject?
- Hosting for the App Proxy backend — what infrastructure is available?
