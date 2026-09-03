# YMAL — Memory

**Purpose of this file:** a running checkpoint log. At every meaningful
checkpoint — a decision made, a component finished, a direction changed — a new
entry gets appended at the top of §3. Reading §2 + the top two entries of §3
should be enough to pick the work back up cold, without re-reading the other
docs.

Newest entry first. Keep entries short. Link out to the other docs instead of
repeating their content here.

---

## 1. One-line summary

Building an in-house "You May Also Like" recommendation system for the Wooden
Ships Shopify store, to replace the Wiser AI app and gain control over the
recommendation logic.

---

## 2. Stable facts (rarely change)

| Thing | Value |
|---|---|
| Shop | `wooden-ships.myshopify.com` |
| Admin API version | `2026-01` |
| Auth pattern | `Setup/set_sy.py` → client_credentials → access token |
| Stack | Python + Shopify Admin GraphQL |
| Current provider | Wiser AI (Shopify app) — still live |
| Team | Web admin team works from the Shopify admin UI |

**Sibling projects worth copying patterns from:**
`Collection VO Automatic Sort` (GraphQL pagination, `Setup/`, `config/`),
`judgeme-review` (connector layout).

**Standing constraints:**
- Web admin team should not need to run Python. Output must land where they
  can see and override it.
- Fashion catalog — the same style in multiple colorways is a real dedupe
  problem.
- Live storefront. Theme changes need a backup and preview path.
- Files sit on a Google Drive shared drive — mind large artifacts.

---

## 3. Checkpoint log

### 2026-09-03 — Checkpoint 5: monorepo + Phase 1 backend written

**Monorepo created:** `backend/` (Python) + `frontend/` (JS, placeholder until
Phase 6) + `docs/`.

**Naming convention decided:** all-lowercase packages and modules, PEP 8.
Deliberately *not* copying the sibling projects' `Setup/` + `config/` mix —
capitalised folders beside lowercase ones are inconsistent and propagate.

```
backend/
├── ymal/          logic — settings, auth, shopify, eligibility, catalog
├── scripts/       entry points, run as `python -m scripts.<name>`
└── data/          outputs (gitignored)
```

`eligibility.py` holds the rule as **pure functions, no I/O** — deliberately,
so the piece the project hinges on can be tested without touching Shopify.

**Phase 1 scripts written and compiling.** Rule verified against sample titles:
`*SALE*` matches, `WHOLESALE` and `Salem` correctly do not (the asterisks are
what make this safe).

**Notable implementation choice:** eligibility needs to know which products are
stocked at Bali. Walking every product's variants → inventory levels multiplies
GraphQL cost past Shopify's 1000-point per-query cap. Instead we query the Bali
*location's* inventory directly and join against the active product list — two
cheap passes rather than one that cannot run.

**Extra guard beyond the stated rule:** `EXCLUDE_UNPUBLISHED` (default on)
drops products with no online-store URL, since a card linking nowhere is a
broken card. Toggle off in settings for the literal two-condition rule.

**Git:** repo initialised, remote added
(`github.com/Wooden-Ships-Knits/ymal-project.git`). `.env` and `backend/data/`
confirmed ignored. **Not committed or pushed** — first commit follows the
branch SOP in `docs/github_SOP.md` §5.

**Security:** a live-looking access token is committed in a sibling project
(`Collection VO Automatic Sort/Setup/set_sy.py`, trailing comment). Should be
rotated. Noted in the SOP so the pattern is not repeated here.

**Next step:** run `python -m scripts.fetch_locations` to confirm the real Bali
location name, set `BALI_LOCATION_PATTERN`, then run `fetch_products`.

---

### 2026-09-03 — Checkpoint 4: phased plan created

`docs/strategy.md` written. Project split into 8 phases, each producing **one
verifiable artifact** with explicit exit criteria — because the real risk here
is assumptions about our own catalog, not code.

**Phase 1 (current) = list active product pages that are unfix.** Nothing else.
No scoring, no widget. Its output closes three of the five open assumptions in
`caveats.md` §5 and produces the eligible-product count that pool depth and
slot count both depend on.

**Parallel track — started outside the phases** because they run on external
clocks: the `read_all_orders` approval request, and capturing Wiser's baseline
while it is still installed.

**Deliberate ordering choice:** content-based recommendations (Phase 3) come
*before* collaborative (Phase 4), so a delayed `read_all_orders` approval cannot
stall the project. Content-based is also the permanent cold-start path.

**Next step:** Phase 1 — build the eligible-product list and diff it against
the Sheet.

---

### 2026-09-03 — Checkpoint 3: eligibility rule defined, Sheet as ground truth

**Eligibility rule agreed** (`logic.md` §4.1). A product may appear in YMAL
only if **both**: stock is replenishable (produced at the **Bali** location)
**and** the title does not contain the marker **`*SALE*`**. Fixed-stock and
markdown products never appear.

The marker is asterisk-delimited — `*SALE*`, not the bare word. Match the full
token. (`*` is a regex metacharacter — escape it or use literal containment.)

**Google Sheet of eligible ("unfix") products.** User will hand-build this.
Its role is deliberately scoped:

- **Now:** ground truth / answer key. We derive eligibility from the API and
  diff it against the Sheet. Match → rule validated. Divergence → the mismatched
  rows show exactly where the rule is wrong.
- **Then:** once validated, the API rule becomes source of truth.
- **After:** Sheet demoted to the merchandiser override list (pins/blocks) —
  which closes a previously open question and reuses the team's existing
  `PPA_SHEET_ID` Sheets pattern.

Keyed on **`product_id`**, not title — titles mutate when `*SALE*` is added,
which is the very event being tracked.

**Two things this unblocks immediately:** the catalog-size risk
(`caveats.md` §2 — how many products survive the filter, which drives pool
depth and slot count), and progress while `read_all_orders` approval is still
pending, since that gates the collaborative signal but not eligibility.

**Proposed but NOT yet confirmed:** phasing the serving model — Phase 1 as
metafield + Liquid filtering (no backend, no hosting; works because the Bali
flag is slow-changing and can be precomputed, while `available` and the title
are both checkable live in Liquid), Phase 2 adding the App Proxy backend for
diversity rules and personalization. This would revise decision #3. Awaiting
user confirmation.

**Next step:** user builds the Sheet. Then count eligible products and diff
against an API-derived list.

---

### 2026-09-03 — Checkpoint 2: architecture settled, strategy agreed

**Key insight this session.** Wiser's observed failure — showing items with
wrong fixed/sale status — is a *timing* failure, not a model failure.
Relevance was computed offline and never re-checked against live state. This
drove the whole architecture.

**Decisions (see §4):** two-stage split — ML relevance offline nightly,
business rules at serve time. App Proxy backend for serving, metafield pool as
degraded fallback. Store a ~30-deep candidate pool, display 6. Tracking ships
in phase 1 because it is training data for learning-to-rank, not just
measurement.

**Confirmed:** everything Wiser does is available to us — Admin API, theme app
extension, App Proxy, Web Pixel, metafields. Platform is not the constraint.

**Scopes identified:** `read_products`, `write_products`, `read_orders`,
`read_all_orders` ⚠️, `read_inventory`, `read_locations`, `read_publications`.
Deferred: `read_customers`, `read_metaobjects`, `read_customer_events`.

**Blocking / time-sensitive:**
- `read_all_orders` needs a Shopify approval request. Without it: 60 days of
  order history only, which is not enough for a seasonal catalog. **Submit now.**
- Capture Wiser's current output as a baseline while it is still installed.

**Open:** exact fixed/sale rule (needs user clarification); hosting for the App
Proxy backend; where merchandiser pins/blocks live.

**Next step:** confirm the fixed/sale rule, then Phase 0 groundwork.

---

### 2026-09-03 — Checkpoint 1: docs scaffolded, discussion opened

- Created `docs/` with `prd.md`, `memory.md`, `backend.md`, `frontend.md`,
  `flow.md`, `logic.md`.
- `backend.md` and `frontend.md` drafted with proposed structure. `flow.md`
  drafted. `logic.md` intentionally left as a stub — to be filled during the
  logic discussion.
- **Nothing built. No code. No decisions locked in yet.**
- Superpowers plugin installed and enabled for this project.

**Open forks blocking the build:**
1. Serving model — precompute to metafields vs live API (`backend.md` §4)
2. Whether we need browsing/view data (needs a Web Pixel) or orders-only
3. How we measure "better than Wiser"

**Next step:** discussion — starting with the PRD and the serving model.

---

## 4. Decisions locked

Append here only when a decision is final. Nothing gets built on a decision
that isn't written down here.

| # | Decision | Rationale | Date |
|---|---|---|---|
| 1 | Build our own app; do not extend Wiser | All required Shopify primitives are public and available to us | 2026-09-03 |
| 2 | Two-stage: ML relevance offline, rules at serve time | Wiser's fixed/sale failure is a staleness problem; rules must see live state | 2026-09-03 |
| 3 | Serve via App Proxy backend, metafield pool as fallback | Same-origin, full rule complexity in Python, degrades safely if backend is down | 2026-09-03 |
| 4 | Store ~30 candidates, display 6 | Filters need headroom or the widget renders thin | 2026-09-03 |
| 5 | Tracking ships in phase 1 | It is training data for learning-to-rank and cannot be collected retroactively | 2026-09-03 |
| 6 | Eligible = Bali location **AND** title lacks `*SALE*` | Never drive demand at stock we cannot replenish, or traffic to markdown | 2026-09-03 |
| 7 | Google Sheet of eligible products = validation set, not source of truth | Gives a hand-verified answer key to diff the automated rule against; manual lists go stale silently | 2026-09-03 |
| 8 | Sheet keyed on `product_id` | Titles mutate when `*SALE*` is added — keying on a field that changes with status is a bug source | 2026-09-03 |
| 9 | Sheet later becomes the merchandiser override list | Closes the open question on where pins/blocks live; matches existing team Sheets workflow | 2026-09-03 |
