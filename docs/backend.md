# YMAL — Backend

Draft for discussion. Follows the conventions already used in
`Collection VO Automatic Sort` and `judgeme-review`.

---

## 1. Stack

Python, matching the rest of the team's work. No new runtime to learn.

```
requests            Shopify Admin GraphQL
pandas              feature tables, co-purchase matrix
scipy / numpy       sparse matrix ops, similarity
```

Deliberately **no ML framework** for v1. Co-occurrence counting plus attribute
similarity is well within pandas/scipy. If we later need embeddings, that's a
v2 conversation with a real reason behind it.

---

## 2. Proposed layout

Mirrors the sibling projects so it's familiar:

```
ymal-project/
├── Setup/
│   └── set_sy.py            # reuse: client_credentials → token
├── config/
│   ├── settings.py          # shop, API version, paths
│   └── weights.py           # blend weights, thresholds, slot count
├── extract/
│   ├── fetch_products.py
│   ├── fetch_orders.py
│   └── fetch_inventory.py
├── build/
│   ├── features.py          # one row per product
│   └── copurchase.py        # order lines → lift matrix
├── score/
│   ├── content.py
│   ├── collaborative.py
│   ├── complete_the_look.py
│   └── blend.py
├── rules/
│   ├── filters.py           # OOS, dedupe, price guard
│   ├── diversity.py
│   └── overrides.py         # merchandiser pins/blocks
├── publish/
│   └── to_metafields.py
├── data/                    # gitignored — raw + intermediate
├── docs/
└── run_pipeline.py          # orchestrator
```

---

## 3. Data extraction

**Products** — Admin GraphQL, cursor-paginated (same pattern as
`fetch_collections.py`). Fields needed:

```graphql
products(first: 100, after: $cursor) {
  edges { node {
    id handle title productType vendor tags status createdAt
    onlineStoreUrl
    collections(first: 20) { edges { node { id handle } } }
    priceRangeV2 { minVariantPrice { amount } }
    totalInventory
    options { name values }
    featuredImage { url }
  } }
}
```

**Orders** — the expensive one. Full history is large; use Shopify's **bulk
operations API** rather than paginating live queries. Extract only:
`order_id, line_item.product_id, quantity, created_at`.

Nightly runs should be **delta** (orders since last run), with the co-purchase
matrix updated incrementally. Full rebuild weekly.

**Inventory** — needed for the availability filter. Can piggyback on the
product query via `totalInventory` if variant-level precision isn't required.

---

## 4. Serving — the main architectural decision

### Option A — Precompute into Shopify metafields ⭐ leaning

Nightly job writes a list of product IDs into a metafield on each product:

```
namespace: ymal
key:       recommendations
type:      list.product_reference
```

Theme reads it directly in Liquid.

**Pros:** no hosting, no cost, no latency, no uptime risk, works with JS
disabled, good for SEO, and the web admin team can *see and edit* the values in
the Shopify admin — which matters given how they work.
**Cons:** not personalized per customer; only as fresh as the last run;
metafield write volume on large catalogs (bulk mutations, batched).

### Option B — Live API service

FastAPI service, theme calls it per pageview.

**Pros:** real-time, personalizable, easy to A/B, no metafield limits.
**Cons:** hosting + monitoring + CORS + a new uptime dependency on the
storefront. If it goes down, the widget breaks.

### Option C — Hybrid

Metafields as the base layer and guaranteed fallback; optional API layer added
later for logged-in personalization, degrading to metafields on failure.

**My recommendation: start with A, keep the door open to C.** It ships fastest,
adds no infrastructure, and the storefront cannot break because of us. We only
take on Option B's complexity if personalization proves it's worth it.
Worth deciding together — this is the fork everything else follows from.

---

## 5. Scheduling

Nightly. Whatever the other automations here already use — if there's an
existing scheduler on this machine or a server, reuse it rather than inventing
one. **Open question: what runs the existing nightly jobs?**

Each run should emit a report:
- products processed / with recommendations / with **zero** recommendations
- average recommendations per product
- diff vs previous run (churn — big swings mean something broke)
- API call count and rate-limit headroom

---

## 6. Shopify API notes

- Admin GraphQL is **cost-based**, not request-count based. Watch
  `extensions.cost.throttleStatus` and back off; the sibling projects already
  paginate politely.
- Metafield writes: use `metafieldsSet` (up to 25 per call) and batch.
- Bulk operations are async — poll for completion, then download the JSONL.
- Pin the API version in `config/settings.py` (`2026-01`) so a Shopify release
  doesn't silently change behavior.

---

## 7. Open questions

- Precompute vs live API (§4) — decide first, everything else depends on it.
- How far back do we pull orders, and where do we store the extract?
- What scheduler runs the nightly job?
- Do we need variant-level stock, or is product-level `totalInventory` enough?
- Where do merchandiser overrides live — Google Sheet or metafields?
- Do we have write scope (`write_products`) on the existing app credentials, or
  is a scope change needed? **Worth checking early — it can block publishing.**
