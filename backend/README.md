# YMAL — Backend (Python)

Pulls from the Shopify Admin GraphQL API, resolves eligibility, and in later
phases generates and publishes recommendations.

## Layout

```
backend/
├── ymal/                 importable package — all logic lives here
│   ├── settings.py       every tunable, including the eligibility rule
│   ├── auth.py           client_credentials -> access token
│   ├── shopify.py        GraphQL client, pagination, throttle backoff
│   ├── eligibility.py    the rule — pure functions, no I/O
│   ├── catalog.py        catalog reads (locations, products, inventory)
│   ├── registry.py       the five blocks, the nine page templates
│   ├── config_schema.py  config validation — pure functions, no I/O
│   └── config_store.py   read/write the ymal.config shop metafield
├── app/                  the console's API (FastAPI)
│   └── main.py           routes and the write-token guard
├── scripts/              runnable entry points
│   ├── fetch_locations.py
│   ├── fetch_products.py
│   └── build_blocks.py
├── tests/                pytest — run from backend/
├── data/                 outputs (gitignored)
└── requirements.txt
```

**Convention:** lowercase module and package names throughout (PEP 8). Logic
goes in `ymal/`, things you run go in `scripts/`. The split keeps
`eligibility.py` free of I/O so the rule can be tested without hitting Shopify.

## Setup

Use a virtualenv. On this machine `python3` resolves to an unrelated venv, so
installing into "the system Python" is not reliable:

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`.venv/` is gitignored. The Docker image ignores all of this and installs
`requirements.txt` directly.

Credentials come from `.env` at the repo root:

```
SHOPIFY_CLIENT_ID=...
SHOPIFY_SECRET_KEY=...
YMAL_API_TOKEN=...
```

Required scopes: `read_products`, `read_inventory`, `read_locations`. Writing
the config metafield additionally needs write access to metafields — **not yet
granted**, so `PUT /api/config` fails until it is.

## Tests

```bash
cd backend && .venv/bin/python -m pytest
```

No network: the eligibility rule, the config validator and the metafield store
all run against known inputs or a stubbed GraphQL client.

## The console API

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload   # localhost:8000
```

Refuses to start without `YMAL_API_TOKEN` in `.env` rather than running open.
Reads need no token; writes send it as `X-YMAL-Token`.

| Endpoint | Does |
|---|---|
| `GET /api/config` | the stored config, plus `updated_at` / `updated_by` as siblings |
| `PUT /api/config` | validates, then writes, keeping the old one as the undo point |
| `POST /api/config/undo` | restores the previous config. One step, not a stack |
| `GET /api/blocks` | the five blocks, each with `list_published` |
| `GET /api/page-templates` | the nine templates, `live` marking the v1 two |

The contract these implement is `docs/config-contract.md`.

## Phase 1

Scripts run as modules from the `backend/` directory:

```bash
cd backend

# 1. confirm the real Bali location name, then set BALI_LOCATION_PATTERN
python -m scripts.fetch_locations

# 2. produce the eligible-product list
python -m scripts.fetch_products
```

Outputs to `backend/data/phase1/`:

| File | Contents |
|---|---|
| `active_products.csv` | one row per active product, with `eligible` + `reason_if_not` |
| `active_products.json` | same, as JSON |
| `summary.json` | counts, plus the rule config that produced them |

## The eligibility rule

Configured in `ymal/settings.py`, implemented in `ymal/eligibility.py`,
documented in `docs/logic.md` §4.1. A product is eligible ("unfix") only if
**both**:

1. it is stocked at the **Bali** production location — replenishable
2. its title does **not** contain **`*SALE*`** — not markdown

`EXCLUDE_UNPUBLISHED` adds a third guard beyond the stated rule: a product with
no online-store URL has nowhere to link, so recommending it would render a dead
card. Set it `False` to apply the literal two-condition rule only.

## Notes

- Admin GraphQL is **cost-based**, not request-count based. `shopify.py` backs
  off when the budget runs low; page sizes in `settings.py` are conservative
  for the same reason.
- `catalog.py` queries the **Bali location's inventory** rather than walking
  every product's variants. Nested connections multiply query cost past
  Shopify's 1000-point per-query cap — two cheap passes avoid that entirely.
- The `*SALE*` check uses literal string containment, never regex. `*` is a
  regex metacharacter, so a compiled `*SALE*` pattern would not match the text
  it appears to.
