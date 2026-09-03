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
│   └── catalog.py        catalog reads (locations, products, inventory)
├── scripts/              runnable entry points
│   ├── fetch_locations.py
│   └── fetch_products.py
├── data/                 outputs (gitignored)
└── requirements.txt
```

**Convention:** lowercase module and package names throughout (PEP 8). Logic
goes in `ymal/`, things you run go in `scripts/`. The split keeps
`eligibility.py` free of I/O so the rule can be tested without hitting Shopify.

## Setup

```bash
pip install -r backend/requirements.txt
```

Credentials come from `.env` at the repo root:

```
SHOPIFY_CLIENT_ID=...
SHOPIFY_SECRET_KEY=...
```

Required scopes: `read_products`, `read_inventory`, `read_locations`.

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
