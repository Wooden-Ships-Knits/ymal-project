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

### 2026-09-04 — Checkpoint 11: frontend/ restored, hierarchy follows wholesale-order-entry

**Reverted checkpoint 10's rename.** `theme/` is `frontend/` again and `console/`
is gone. Two top-level folders, `backend/` and `frontend/`, and they stay that
way.

**Both JavaScript surfaces live in `frontend/`:**

```
frontend/
├── src/          the console (React + Vite) — one folder per tab
└── storefront/   Liquid snippet + the JS that runs on wooden-ships.com
```

**Structure copied from `wholesale-order-entry`**, the closest sibling project —
same team, same shape, already deployed:

- React 18 + Vite, **no router**. Tabs are `useState` plus a `TABS` array and a
  conditional render, exactly as `frontend/src/admin/AdminApp.jsx` does it there.
- A folder per feature holding its screens **and its own `api.js`**
  (`setup/`, `analytics/`, `exclude/`).
- Shared pieces in `components/`, pure helpers in `lib/`.
- `Dockerfile` + `nginx.conf` inside `frontend/`, serving the built static files.
- Only `VITE_API_BASE` in its `.env` — never a Shopify credential.

Adding a tab is one folder, one `TABS` entry, one conditional render.

**Naming lesson worth keeping:** "frontend" was used as both a layer label in a
table and a directory name within a few messages, which made an approved rename
look like a contradiction. When a word names both a concept and a path, say
which one is meant.

**Next step:** the five-minute Liquid test — confirm a shop-level
`list.product_reference` metafield resolves to product objects in Liquid the way
a product-level one does. Section 2 of the config contract rests on it.

---

### 2026-09-04 — Checkpoint 10: repo split, config contract written

**Repo split.** `frontend/` meant one thing when there was one frontend; there
are now two:

```
theme/     Liquid + storefront JS   — what the shopper sees
console/   FastAPI + JavaScript     — what the web team uses
```

`git mv frontend theme`, both READMEs rewritten, `console/` created. Root README
layout and docs table updated.

**`docs/config-contract.md` written** — the keystone document. Contents: every
metafield in the system; the `ymal.config` schema with a worked example; the
five-block registry with a which-block-on-which-page matrix; the ten validation
rules; versioning and one-click undo; what the Liquid snippet does; the console's
API surface; and what deliberately stays in `settings.py` rather than becoming a
console knob.

**Two design points worth remembering:**

1. **Publish lists as `list.product_reference`.** Liquid then gets live product
   objects, so a list written at 03:00 cannot render yesterday's price — and the
   pipeline never needs `featuredImage` or `priceRangeV2`. **Verify early** that
   a *shop-level* reference list resolves to product objects in Liquid the way a
   product-level one does; the design rests on it and it is a five-minute test.
2. **The console validates and rejects rather than repairs.** A malformed config
   silently blanks every block and nobody notices until traffic drops.

**Still nothing committed** — the whole reframe (checkpoints 6-10) is sitting in
the working tree on `feat/dev-environment`.

**Next step:** run the five-minute Liquid metafield test, then either start the
console API or add `tags` + `publishedAt` to the product query.

---

### 2026-09-04 — Checkpoint 9: console stack decided

**No Streamlit.** The console is a real web page: **JavaScript frontend, FastAPI
backend, deployed exactly the way PPA's console is** — Docker on the existing VM,
behind the host nginx, password-gated.

- The FastAPI layer lives in this repo and imports the `ymal` package directly,
  so the console reuses `auth.py`, `shopify.py` and `eligibility.py` rather than
  reimplementing them.
- **Shopify credentials never reach the browser.** The JS page calls our API; our
  API talks to Shopify.
- Roughly four screens, so React-with-a-build and plain-JS-no-build are both
  viable. Not yet decided, and not blocking.

**Shopify embedded app rejected for now, not forever.** It would sit inside the
Shopify admin and look native, but it needs App Bridge, session-token auth inside
an iframe, an app registration and a Node stack nobody on the team runs — weeks,
not days. Because the console's only job is writing the `ymal.config` metafield,
it can be replaced later without touching the pipeline or the theme.

**Repo split needed.** `frontend/` currently describes only the storefront widget.
There are now two frontends:

```
theme/     Liquid snippets + storefront JS (what shoppers see)
console/   the admin app (what the web team uses)
```

**Recently Viewed needs no tracking pipeline.** The browser remembers it itself:
a few lines of JS append `{handle, id, ts}` to `localStorage` on each product
page, and the block reads that list back and renders from it. It never leaves the
device, needs no login, and works for logged-out shoppers. Per-browser by nature —
a different phone is a different list — and empty in a fresh or private browser,
where the block must hide itself. This is almost certainly how Wiser does it too.

**Next step:** design the config contract (`ymal.config`), then split the repo
into `theme/` and `console/`.

---

### 2026-09-04 — Checkpoint 8: the real deliverable is an admin console

User shared a screenshot of **Wiser's "Active Widgets" screen** and named the two
halves of the project explicitly:

> **Backend** — handles the logic and fetches the data.
> **Frontend** — an interface like the screenshot, where the web team can adjust
> placement and see how much we profit.

**This is three deliverables, not two.** A nightly pipeline, a storefront
integration, and an internal console with an event store behind it. The
recommendation logic is the smallest part of the work.

**The keystone is a config contract**, not the UI. One shop metafield
(`ymal.config`) holds, per page template, which blocks appear in what order with
how many slots. The console writes it, Liquid reads it, the pipeline never
touches it. That single fact is what lets the web team re-arrange the storefront
with no deploy and no Liquid edit — which is the actual point of Wiser's screen.
**Design it before writing any of the three layers.**

**Publish the lists as `list.product_reference`, not our own JSON.** Liquid then
receives live product objects, so a list written at 03:00 cannot render
yesterday's price — and we never need to fetch `featuredImage` or
`priceRangeV2` at all.

**Console stack — open, and it decides the next several weeks.** PPA already
runs a Streamlit app in Docker behind the VM's nginx, password-gated, with a
companion hourly fetch service (`PPA/webapp/`, `docker-compose.yml`,
`deploy/ppa.nginx.conf`). Reusing that answers auth, deploy and scheduling on day
one, but will not look like the screenshot. A Shopify embedded app (Remix +
Polaris) would, at the cost of a new stack and weeks instead of days.
Recommended: Streamlit now, embedded app later if the look matters — the config
metafield means the console can be swapped without touching the other layers.
*(If reusing PPA's pattern: do not inherit its plaintext default password, which
its own compose file flags as needing changing.)*

**Attribution is the hardest part, and it is honest-number-hard, not
code-hard.** Matching a click to an order measures what a block *touched*, not
what it *caused*. The only truthful answer to "how much do we profit" is a
**holdout** — a stable hash of session id keeps ~10% of sessions block-free — and
it cannot be applied retroactively. It must be switched on with the first block
that ships, exactly like the Wiser baseline we already know we must not lose.
Also: "profit" needs cost. Shopify carries `unitCost` on InventoryItem — check
whether PPA populates it, or report revenue and do not imply margin.

**Decision #3 (App Proxy) is now superseded**: lists live in metafields and
Liquid reads them, so nothing sits in the request path. We still need hosting,
but for the console and the event endpoint. **Decisions #7-9 partly superseded**:
the merchandiser override list belongs in the console's Exclude Products screen,
not a Sheet that drifts.

**`docs/ymal-flow.drawio` rebuilt to 9 pages**, adding Admin Console, Config
Model / Storefront Contract, and Attribution.

**Next step:** pick the console stack, then design the config contract. Both are
decisions, not code, and everything else waits on them.

---

### 2026-09-04 — Checkpoint 7: goal reframed — a widget SET, not one recommender

**The goal changed.** Not "build a smarter You May Also Like" but "match Wiser's
set of blocks". Five blocks:

| Block | Rule | Scope |
|---|---|---|
| Trending | order line items, last **14 days**, ranked by quantity | store-wide |
| Top Selling | same code, **90-day** window | store-wide |
| New Arrivals | `publishedAt` within the last 30 days | store-wide |
| Featured | other products sharing tags with the current product page | per product |
| Recently Viewed | the shopper's own last N views | per visitor |

**What this does to the architecture.** Three of the five are ONE list for the
whole store, not a list per product. That removes the 30-deep per-product pool,
the ~254 metafield writes, the `metafieldsSet` batching problem, and most of the
argument for an App Proxy backend. Only Featured needs per-product storage;
Recently Viewed needs no backend at all. There is no ranking
model here to train: Trending is a sort.

**Decision #4 (30-deep pool) is superseded** for four of five blocks; the
principle behind it — store roughly 3x what you display — still holds.
**Decision #3 (App Proxy) is weakened**: Liquid can read a shop metafield
directly, so nothing needs to sit in the request path. **Decision #6 (the
eligibility rule) is promoted** — it is now the single shared gate behind four
blocks, so validating it once pays four times.

**Three findings from the sibling projects:**

1. `PPA/` is Product Page Automation, and `Setup/tags_generator.py` **generates
   the tags deterministically** from the style name — composition, ply, sleeve,
   type, pattern, features, neck. The "tag quality is unaudited" risk in
   `caveats.md` is largely dead.
2. **`tags[0]` is the style itself**, so every colorway of one style carries the
   same tag. That is the colorway-dedupe key, already in the data.
3. But every product also gets `sweater, sweaters, sweatshirt, outfit, outfits,
   casual` — near-universal tags with no discriminating power. Tag similarity
   must weight by rarity or those swamp every score. **Measure tag frequency
   across the 254 eligible products before building Featured.**

**Two problems found while planning, both needing a decision before code:**

- **The 60-day order cap bites Top Selling, not Trending.** 14 days sits inside
  the window every app gets; 90 days does not. Recommended: request approval AND
  start banking daily order snapshots now — the snapshot is the only option that
  cannot be started retroactively.
- **Trending and Top Selling will return nearly the same products.** A 14-day
  bestseller is usually a 90-day bestseller. Either dedupe across blocks at
  render, or redefine Trending as *rising* — this period's units versus the
  previous period.

**`docs/ymal-flow.drawio` rewritten** around the five blocks (6 pages). The
previous ML-architecture version is not in git history; it is regenerable if the
goal ever widens back.

**Next step:** settle the Trending/Top Selling overlap question, start the daily
order snapshot, then add `tags` and `publishedAt` to the product query and count
tag frequency.

---

### 2026-09-04 — Checkpoint 6: anchor diagram created

`docs/ymal-flow.drawio` — six pages covering the whole project, built from the
docs plus the Phase 1 output rather than from a fresh guess:

1. **System Overview** — the two-clock architecture (nightly relevance / serve-time
   eligibility), with the boundary drawn explicitly and the tracking feedback loop
   back into relevance.
2. **Phase Plan** — the eight phases, their exit criteria, and the parallel track
   (`read_all_orders`, Wiser baseline, the Sheet) wired to the phases it gates.
3. **Eligibility Rule** — the rule as built, as a decision flow, carrying the real
   numbers: 392 active, 254 eligible (64.8%), 126 fixed_stock, 118 sale_marker.
4. **Serve-Time Flow** — one pageview end to end, plus the degraded path and the
   five-level fallback chain.
5. **Code Map** — every module that exists, what it does, and the ones still to
   be written.
6. **Decisions** — the nine locked decisions, the external blockers, and every
   open question, sorted by who has to answer it.

**Kept as uncompressed XML on purpose.** The file is meant to be pasted back
into an LLM prompt as project context, so it has to stay readable and greppable
rather than base64-compressed the way draw.io saves by default. Colour is a
status legend, not decoration: green is built, blue is planned, red is blocked,
amber is an open question.

**Stale doc corrected while doing this:** the root README still said
`BALI_LOCATION_PATTERN` "currently defaults to the guess `bali`". It has been
`"bali to produce"` since the location names were confirmed.

**Next step:** unchanged — diff the 254-row API list against the hand-built
Sheet, which closes Phase 1 and three of the five open assumptions in
`caveats.md` §5.

---

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
