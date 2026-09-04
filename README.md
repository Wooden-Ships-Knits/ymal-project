# YMAL — You May Also Like

In-house product recommendation engine for the Wooden Ships Shopify store,
replacing the Wiser AI app so we control the recommendation logic.

**Status: Phase 1 of 8.** No recommendations are generated yet, and nothing is
live on the storefront. Phase 1 produces the eligible-product list that
everything else is built on.

---

## Why we are building this

Wiser works, but it is a black box: we cannot see why a product was
recommended, cannot encode our own product knowledge, and cannot stop it
surfacing products we do not want surfaced. The concrete failure that drove
this project was Wiser showing fixed-stock and markdown items in the widget.

That turned out to be a timing problem rather than a model problem — relevance
was computed once and never re-checked against live stock and price state. The
architecture here splits the two apart:

| Layer | Question | Runs |
|---|---|---|
| Relevance | Which products are related to this one? | Nightly, offline |
| Eligibility | Which of those may we show right now? | Serve time, on live state |

See `docs/flow.md` for the full picture.

---

## Repository layout

```
ymal-project/
├── backend/          Python — the pipeline, plus the FastAPI the console calls
│   ├── ymal/         importable package (settings, auth, shopify, eligibility, catalog)
│   ├── scripts/      runnable entry points
│   └── data/         outputs (gitignored)
├── frontend/         JavaScript — both of the things shoppers and staff see
│   ├── src/          the console (React + Vite), one folder per tab
│   └── storefront/   the Liquid snippet + the JS that runs on the live store
├── docs/             PRD, strategy, flow, logic, caveats, config contract, SOP, memory
└── docker-compose.yml
```

## Running it

```bash
# the pipeline, directly - fastest loop, no container build
cd backend && python -m scripts.fetch_products
cd backend && python -m scripts.build_blocks

# the console, in dev
cd frontend && npm install && npm run dev      # localhost:5173

# everything, in Docker (from a LOCAL clone, not the Drive folder)
docker compose up web                          # console on 127.0.0.1:8083
docker compose run --rm pipeline               # rebuild the block lists
docker compose --profile api up                # once backend/app exists
```

Docker is for the server. Keep running the pipeline directly while developing -
`python -m scripts.<name>` takes seconds, and putting a container build in front
of that only slows the loop.

Frontend structure follows `wholesale-order-entry`: React 18 + Vite, no router,
tabs are `useState` plus a `TABS` array, one folder per feature with its own
`api.js`.

The three layers are joined by one settings document — see
`docs/config-contract.md`. The console writes it, the storefront reads it, the
pipeline never touches it.

---

## Setup

Requires Python 3.10 or newer.

```bash
pip install -r backend/requirements.txt
```

Create `.env` at the repository root (it is gitignored - never commit it):

```
SHOPIFY_CLIENT_ID=...
SHOPIFY_SECRET_KEY=...
```

The Shopify custom app needs these scopes for Phase 1:

- `read_products`
- `read_inventory`
- `read_locations`

Later phases additionally need `write_products` (to publish recommendations)
and `read_orders` plus `read_all_orders`. **`read_all_orders` requires an
approval request to Shopify** and without it order history is capped at 60
days, which is not enough for a seasonal catalog. Submit that request early -
it is the longest-lead item in the project.

---

## Phase 1 — Eligible product inventory

**Goal:** know exactly which active product pages are eligible ("unfix") to
appear in the recommendation widget.

### The eligibility rule

A product is eligible only if **both** conditions hold:

1. It is stocked at the **Bali** production location, meaning stock is
   replenishable rather than fixed.
2. Its title does **not** contain the marker `*SALE*`.

Anything fixed-stock or on markdown is excluded. The rule lives in
`backend/ymal/eligibility.py` as pure functions with no I/O, so it can be
tested without calling Shopify. Its configuration is in
`backend/ymal/settings.py`.

There is a third guard beyond the two stated conditions:
`EXCLUDE_UNPUBLISHED` (on by default) drops products with no online-store URL,
since a recommendation card that links nowhere is a broken card. Set it to
`False` for the literal two-condition rule.

### How to run

Scripts run as modules from the `backend/` directory.

**Step 1 — confirm the Bali location name.**

```bash
cd backend
python -m scripts.fetch_locations
```

This lists every location on the shop and reports which ones match
`BALI_LOCATION_PATTERN` in `ymal/settings.py`. That pattern is set to
`"bali to produce"`, confirmed against the live shop on 2026-09-03 — the full
name, not just `"bali"`, because `Bali Stock` is a separate fixed-stock
location that must not match. Re-run this step if the locations change.

**Step 2 — produce the eligible-product list.**

```bash
python -m scripts.fetch_products
```

If no location matches the pattern, this script refuses to run rather than
silently classifying the entire catalog as fixed stock.

### Outputs

Written to `backend/data/phase1/`:

| File | Contents |
|---|---|
| `locations.json` | Every Shopify location |
| `active_products.csv` | One row per active product, with `eligible` and `reason_if_not` |
| `active_products.json` | The same data as JSON |
| `summary.json` | Counts, plus the rule configuration that produced them |

### Exit criteria

Phase 1 is done when:

1. The list has been produced from the Admin API.
2. It has been diffed against the hand-built Google Sheet of eligible products
   (see `docs/caveats.md` section 0).
3. Any discrepancies are explained, or the rule is corrected and re-run.
4. **The eligible-product count is known.** This number drives candidate pool
   depth and widget slot count, both of which are provisional guesses until it
   exists.

---

## Roadmap

| Phase | Deliverable |
|---|---|
| 1 | Eligible product list (current) |
| 2 | Product feature table |
| 3 | Content-based recommendations |
| 4 | Collaborative signal (needs `read_all_orders`) |
| 5 | Publish to Shopify metafields |
| 6 | Storefront widget and tracking |
| 7 | A/B test against Wiser |
| 8 | Machine-learning upgrade |

Content-based recommendations deliberately come before the collaborative
signal, so a slow `read_all_orders` approval cannot stall the project.
Nothing reaches a customer until Phase 6, and Wiser stays installed until
Phase 7 produces evidence to remove it.

Full detail, including exit criteria per phase, is in `docs/strategy.md`.

---

## Documentation

| File | Contents |
|---|---|
| `docs/prd.md` | Background, goals, requirements, risks |
| `docs/strategy.md` | The eight phases and their exit criteria |
| `docs/flow.md` | End-to-end data flow, batch and request paths |
| `docs/logic.md` | Recommendation logic, including the eligibility rule |
| `docs/backend.md` | Backend structure and extraction approach |
| `docs/frontend.md` | Widget integration, placements, tracking |
| `docs/caveats.md` | Unverified assumptions, platform limits, risks |
| `docs/memory.md` | Checkpoint log and locked decisions |
| `docs/config-contract.md` | **The contract between console, theme and pipeline** |
| `docs/github_SOP.md` | Branching and commit workflow |
| `docs/ymal-flow.drawio` | Anchor diagram — the whole project on six pages |

New to the project? Read `docs/memory.md` first — the stable facts plus the
top two checkpoints are enough to pick up the work cold.

**`docs/ymal-flow.drawio` is the anchor.** Open it in draw.io (or the VS Code
Draw.io extension). Six pages:

| Page | Answers |
|---|---|
| 1. System Overview | The three layers — pipeline, storefront, console — and the config metafield that joins them |
| 2. Block Specs | What each of the five blocks queries, computes and stores |
| 3. The Shared Eligibility Gate | The rule as built, with the real counts, and which blocks it applies to |
| 4. Data, Windows and Storage | What we fetch, the 60-day order cap, where each list lives |
| 5. Admin Console | The Wiser Setup Widgets screen rebuilt: page-template cards, what Setup contains, stack options |
| 6. Config Model and Storefront Contract | The `ymal.config` schema, every metafield, and what the Liquid snippet does |
| 7. Attribution and Analytics | Events, the attribution model, and why a holdout is the only honest profit number |
| 8. Build Order and Code Map | Ten build steps, what exists, what is still to write |
| 9. Decisions | Locked decisions re-read after the reframe, blockers, open questions |

It is stored as uncompressed XML on purpose: it stays greppable, and a page can
be pasted straight into an LLM prompt as project context. When asking an LLM to
work on this project, give it the relevant page plus `docs/memory.md` section 2
and the top of section 3.

---

## Contributing

All work goes through `feat/*` branches merged into `feat/dev-environment`.
`main` is never pushed to directly. See `docs/github_SOP.md`.

Never commit `.env`, access tokens, or anything under `backend/data/`.
