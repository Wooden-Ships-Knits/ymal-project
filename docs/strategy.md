# YMAL — Strategy

**Created 2026-09-03.** How the project is sequenced and why.

---

## 1. Principle

Every phase produces **one concrete artifact** and has **exit criteria** that
can be checked. A phase is not "build the backend" — it is "produce this file,
and here is how we know it is right."

Rationale: the riskiest parts of this project are assumptions about our own
catalog, not code. Phasing by artifact forces each assumption to be tested
before anything is built on top of it.

**Rule:** do not start phase N+1 while phase N's exit criteria are unmet.
The one exception is the parallel track below.

---

## 2. Parallel track — start now, blocks nothing

Two items have **external clocks**. They do not belong to any phase because
waiting for a phase to reach them wastes calendar time.

| Item | Why it can't wait |
|---|---|
| **`read_all_orders` approval request** | Shopify's turnaround, not ours. Gates all collaborative signal (Phase 4). Without it: 60 days of history only. |
| **Capture Wiser's current output + performance** | Only possible while Wiser is installed. Once removed, the baseline is gone permanently and we can never prove improvement. |

Both should be in motion before Phase 1 finishes.

---

## 3. Phases

### Phase 1 — Eligible product inventory ⬅ **current**

**Goal:** know exactly which active product pages are "unfix" (eligible).

**Deliverable:** a list of active products with eligibility resolved.

| Column | Note |
|---|---|
| `product_id` | Key — immutable |
| `handle` | Human reference |
| `title` | For the `*SALE*` check |
| `locations` | Which locations hold stock |
| `eligible` | Bali **AND** no `*SALE*` |
| `reason_if_not` | `fixed_stock` / `sale_marker` / `inactive` |

**Exit criteria:**
1. List produced from the Admin API.
2. Diffed against the hand-built Google Sheet (`caveats.md` §0).
3. Discrepancies either explained or the rule corrected and re-run.
4. **Eligible product count known** — this number drives pool depth and slot
   count, both currently provisional.

**Unblocks:** the eligibility rule (`logic.md` §4.1) stops being an assumption.
Catalog-size risk (`caveats.md` §2) becomes a known quantity.

**Not in this phase:** no recommendations, no scoring, no widget. Just the list.

---

### Phase 2 — Product feature table

**Goal:** one row per eligible product, with everything scoring needs.

**Deliverable:** feature table — style/colorway grouping, product type, tags,
price band, collections, season, launch date, sales velocity.

**Exit criteria:** every eligible product has a row; colorway grouping verified
by spot-check (this drives style dedupe, and getting it wrong is visible to
customers); tag coverage measured, not assumed.

**Unblocks:** content similarity. Also delivers the tag-quality audit that
`caveats.md` §5 has been carrying as an open risk.

---

### Phase 3 — Content-based recommendations

**Goal:** first working recommendations, without needing order history.

**Deliverable:** ~30-deep candidate pool per eligible product, from attributes
and content similarity only.

**Exit criteria:** every eligible product has a pool; pools contain only
eligible products; manual review of ~20 anchors says the results are sensible.

**Why before collaborative:** it does not depend on the `read_all_orders`
approval. If that gets delayed, this phase still ships and the project keeps
moving. It is also the permanent cold-start path for new products.

---

### Phase 4 — Collaborative signal

**Goal:** add "customers who bought this also bought."

**Depends on:** `read_all_orders` approval.

**Deliverable:** co-purchase scores blended into the existing pools.

**Exit criteria:** offline evaluation against held-out orders beats Phase 3
alone; cold-start fallback confirmed working for low-history products.

---

### Phase 5 — Publish

**Goal:** recommendations reach Shopify.

**Deliverable:** nightly job writing pools + the eligibility flag to metafields,
with a run report (coverage, pool depth, churn vs previous run).

**Exit criteria:** full catalog published; report shows no product below
minimum pool depth; job re-runnable and idempotent.

---

### Phase 6 — Widget + tracking

**Goal:** shoppers see it, and we can measure it.

**Deliverable:** theme snippet or app extension rendering the widget, with
serve-time eligibility filtering, plus impression/click/ATC tracking.

**Exit criteria:** theme backed up; previewed before publish; kill switch
working; no `*SALE*` or fixed-stock item appears in any tested widget; tracking
events confirmed landing.

**Tracking is not optional here.** It is the training data for Phase 8 and
cannot be collected retroactively.

---

### Phase 7 — Prove it

**Goal:** evidence that we beat Wiser.

**Deliverable:** A/B result on the agreed metric.

**Exit criteria:** both widgets ran in parallel on split traffic long enough
for a real read; decision made on the numbers.

**Wiser stays installed until this phase passes.** If ours underperforms, the
fallback must still exist.

---

### Phase 8 — ML upgrade

**Goal:** learning-to-rank trained on our own click data.

**Depends on:** enough tracking data from Phase 6 — likely months.

**Deliverable:** a model that blends signals better than hand-tuned weights.

Optional extensions: image embeddings for visual/silhouette similarity (likely
the highest-value addition for a fashion catalog), and personalization from
customer history.

---

## 4. Dependency map

```
parallel track ──────────────────────────────┐
  read_all_orders request ───────────────┐   │
  capture Wiser baseline ────────────┐   │   │
                                     │   │   │
Phase 1  eligible list               │   │   │
   ↓                                 │   │   │
Phase 2  feature table               │   │   │
   ↓                                 │   │   │
Phase 3  content recs                │   │   │
   ↓                                 │   ▼   │
Phase 4  + collaborative ◄───────────┼───┘   │
   ↓                                 │       │
Phase 5  publish                     │       │
   ↓                                 │       │
Phase 6  widget + tracking           │       │
   ↓                                 ▼       │
Phase 7  A/B vs Wiser ◄──────────────┘       │
   ↓                                         │
Phase 8  ML upgrade ◄────────────────────────┘
         (needs Phase 6 tracking data)
```

---

## 5. What this sequencing buys

- **Phase 1 is small and answers the most questions per unit of effort.** Three
  of five open assumptions in `caveats.md` §5 close on its output.
- **The `read_all_orders` gate cannot stall the project.** Phase 3 ships
  without it; Phase 4 picks it up whenever approval lands.
- **Nothing reaches customers until Phase 6**, by which point the eligibility
  rule has been validated twice — against the Sheet, and at serve time.
- **We never lose the ability to fall back to Wiser** until Phase 7 gives us
  evidence not to.

---

## 6. Open

- Confirm the Phase 1 / Phase 2 serving split proposed in `memory.md`
  checkpoint 3 (metafield + Liquid first, App Proxy later).
- Hosting for the App Proxy backend, if and when Phase 2 of serving arrives.
- Agreed success metric for Phase 7 — still TBD in `prd.md` §5.
