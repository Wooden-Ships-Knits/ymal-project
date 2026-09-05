# YMAL — The Console API

**Created 2026-09-05.** The third layer: the API the console talks to.

The console exists and renders. The config contract is written. This is the
piece between them — the thing that turns Setup Widgets from a layout into a
tool that changes the storefront.

Read `docs/config-contract.md` first. This document implements it and does not
restate it.

---

## 1. What problem this solves

Open the console today and Setup Widgets shows a red banner: **"Not connected
to the backend"**, `Request failed (500)`. Nine page-template cards render, all
saying "No blocks placed". Clicking Setup and saving does nothing, because
`PUT /api/config` has no server behind it.

Everything around that gap is already built:

| Piece | State |
|---|---|
| `frontend/vite.config.js` | proxies `/api` to `localhost:8000` in dev |
| `frontend/nginx.conf` | proxies `/api/` to `api:8000`, lazy DNS so it boots without the API |
| `docker-compose.yml` | `api` service defined, profile-gated until `backend/app` exists |
| `backend/Dockerfile` | comment says the `api` service overrides CMD with uvicorn |
| `frontend/src/api.js` | fetch wrapper, already surfaces 422 field errors intact |

Missing: `backend/app/`, `fastapi` and `uvicorn` in requirements, and the
Shopify metafield read/write.

---

## 2. Decisions taken

Settled during brainstorming on 2026-09-05. Recorded here because each one
closes off an alternative someone will otherwise re-open.

| Decision | Chosen | Why |
|---|---|---|
| Where config lives | The Shopify `shop.ymal.config` metafield, directly | One source of truth. The theme reads the document the console wrote. Postgres or a JSON file would mean two copies that drift, and building the metafield write later anyway. |
| Endpoint scope for v1 | Config, undo, and the two registries | Makes Setup Widgets genuinely work. `/api/analytics` needs an event store that is Phase 6/7 work. |
| Auth | A shared token in `.env`, required on writes | Fifteen lines. Makes the API's own requirements explicit rather than implicit in an nginx config this repo cannot see. |

### Why the metafield write is safe to build now

Nothing in this repo touches the live storefront. YMAL becomes visible to a
shopper only when someone edits the theme — copies the Liquid in and adds a
`{% render %}` tag. `frontend/storefront/install.md` is instructions nobody has
run.

A metafield is inert storage. Liquid sees it only if a theme explicitly reads
`shop.metafields.ymal.config`, and no theme does. Writing it is putting a file
in a folder nobody opens. The `ymal` namespace is ours; Wiser has its own, so
there is nothing of Wiser's to overwrite.

---

## 3. Architecture

Logic in `ymal/`, things you run outside it — the convention `backend/README.md`
already states. The HTTP layer holds no rules.

```
backend/
├── app/
│   ├── __init__.py
│   └── main.py             FastAPI app, routes, auth dependency
└── ymal/
    ├── config_store.py     NEW — read/write the shop metafield
    ├── config_schema.py    NEW — validation. Pure functions, no I/O.
    └── registry.py         NEW — the five blocks, the nine page templates

frontend/src/
├── auth/
│   ├── useToken.js         NEW — the token in sessionStorage
│   └── TokenPrompt.jsx     NEW — password field, shown on 401
└── api.js                  CHANGED — put/post send the token header
```

`config_schema.py` is I/O-free on purpose, mirroring the split that keeps
`eligibility.py` testable without calling Shopify. Every rule in
`config-contract.md` §6 becomes a unit test that runs offline.

`requirements.txt` gains `fastapi` and `uvicorn[standard]`.

### Request path

```
browser → /api/config
        → nginx (prod) or vite proxy (dev)
        → app/main.py
        → ymal/config_schema.py   validate, reject on failure
        → ymal/config_store.py    read/write metafield
        → ymal/shopify.py         GraphQL, throttle backoff
        → Shopify Admin API
```

The browser never holds a Shopify credential. It asks our API; our API asks
Shopify.

---

## 4. Endpoints

Shapes come from `config-contract.md` §9 and are not re-specified here. What
follows is behaviour that document leaves open.

### GET /api/config

```json
{ "config": { ... }, "has_previous": true }
```

A missing metafield is **not** an error. On a shop that has never been written
to there simply is no document, and the correct response is an empty config
with `has_previous: false`. The console already renders that state.

Failure to reach Shopify **is** an error, and must not be flattened into "empty
config" — that is the difference between "no blocks are placed" and "we cannot
tell you what is placed", and `SetupWidgets.jsx` was written to distinguish
them.

### PUT /api/config

1. Validate. Invalid returns 422 with the contract's error array and writes
   nothing.
2. Copy current `ymal.config` to `ymal.config_previous`.
3. Write the new document, stamping `updated_at` and `updated_by` server-side.

Previous is copied **before** the new write, so a failure on step 3 leaves a
recoverable state rather than a lost one.

`updated_at` and `updated_by` are set by the server and rejected if the client
sends them. A client-supplied audit field is not an audit field.

### POST /api/config/undo

Swaps `config_previous` into `config`. Undo is not itself undoable in v1: it
does not push the pre-undo document into `config_previous`. Two metafields
model one step of history, and pretending otherwise invites someone to undo
twice expecting to go back two steps.

Returns 409 if there is no previous document.

### GET /api/blocks

Served from `ymal/registry.py`. `list_published` reports whether the pipeline's
metafield for that block exists on the shop.

Today none do — publishing is Phase 5 — so all three report `false`. That is
useful rather than embarrassing: it lets the console say *"Trending is enabled
on 2 pages but no list has been published yet"*, which is exactly the failure
that would otherwise be discovered on the storefront.

`recently_viewed` has no metafield and no pipeline list. Its `list_published`
is `true` — it has nothing to publish and always works.

### GET /api/page-templates

The nine from `config-contract.md` §5, with `live` marking the two that ship in
v1 (`product`, `home`).

---

## 5. Validation

Every rule in `config-contract.md` §6, returning that document's error shape:

```json
{ "errors": [ { "path": "placements.product[1].slots",
                "message": "must be between 2 and 12" } ] }
```

Two properties matter more than the individual rules:

- **Reject, never repair.** A config quietly "fixed" on the way in is a config
  the console is no longer showing the truth about.
- **Reject unknown fields.** A typo in a field name must fail loudly, not be
  silently ignored while the web team believes it took effect.

`frontend/src/api.js` already lifts `body.errors` onto the thrown error, so
field-level messages reach the console with no frontend change.

### Page-template rules

The allowed block/template matrix lives in `config-contract.md` §4 and is
enforced server-side. The console's `blockAllowedOn` in
`lib/pageTemplates.js` derives the same answer from `requiresAnchor`, and the
two agree today. The server is authoritative: a console bug must not be able to
write a configuration that renders nothing.

---

## 6. Auth

`YMAL_API_TOKEN` in `.env` at the repo root, added to `.env.example`.

| Method | Requires token |
|---|---|
| `GET` | no |
| `PUT`, `POST` | yes |

Sent by the console as an `X-YMAL-Token` request header.

### How the token reaches the browser

**Not through the bundle.** `frontend/.env.example` states the rule: anything
named `VITE_*` is compiled into the JavaScript and readable by anyone who opens
the page. A shared token baked in that way is a public token.

Instead the console prompts for it:

- A password field appears when a write returns 401.
- The value is held in `sessionStorage`, not `localStorage` — it dies with the
  tab rather than persisting on a shared machine.
- It is sent on writes only, and never logged.

This is a login prompt in everything but name, and it adds a small piece of
frontend work not present elsewhere in this spec: a `useToken` hook and a
prompt component, plus threading the header through `api.js`'s `put` and
`post`.

The alternative considered and rejected: have nginx inject the header
server-side, so the browser never holds it. That is simpler, but it makes
access control entirely nginx's job again and the API's token becomes
decoration — which is the outcome choosing a token in the first place was meant
to avoid.

**The API refuses to start if the variable is unset.** It does not fall back to
running open. This follows `fetch_products`, which refuses to run when no
location matches the Bali pattern rather than silently classifying the whole
catalog as fixed stock — a service that fails to start is a visible problem; a
service quietly running without auth is not.

The threat this closes is not the config document. It is that the API holds the
Shopify credentials and acts with the app's permissions: anyone who can call it
can make it write to the shop without ever seeing a credential. That grows more
valuable every phase.

Reads are open because the API binds to no published port — only the `web`
container does, and only on `127.0.0.1` — so a reader is already inside the VM.

**Not per-person.** One shared secret, so `updated_by` records a team rather
than a name. If `wholesale-order-entry` turns out to have a real login on the
same VM, switching to it is strictly better and should be done.

---

## 7. Registries: two copies, deliberately

`frontend/src/lib/blocks.js` and `lib/pageTemplates.js` stay where they are, as
a static fallback. The API's copy wins when it loads and adds `list_published`,
which the frontend cannot know on its own.

The duplication is accepted for its failure mode. Delete the frontend copies
and an API outage gives a blank console; keep them and it degrades to exactly
what the console shows today — cards rendered, banner shown, nothing pretending
to be live state.

If the two ever disagree, the server is right. Adding a block means editing
both, and `blocks.js` already carries a comment saying adding one there without
a backend counterpart produces a page configuring something nothing computes.

---

## 8. Testing

### Automated

`pytest` over `config_schema.py`: every §6 rule, valid and invalid, no network.
This is the first test suite in the repo. `config_store.py` and `app/main.py`
are not unit-tested in v1 — they are thin, and the useful test of them involves
a real Shopify shop.

### Manual smoke

1. Start the API. Confirm it refuses to start with `YMAL_API_TOKEN` unset.
2. Open the console. The red banner should be **gone**.
3. Place Trending on the Home Page, heading "Trending Now", 8 slots. Save.
   The token prompt appears. Enter a wrong password: the save is refused and
   nothing is written. Enter the right one: it saves.
4. Reload. The placement persists, and the token is asked for again on the next
   write in a new tab but not in this one.
5. Read `shop.ymal.config` in the Shopify admin. The document matches what the
   console shows.
6. Undo. The placement reverts, in the console and on the shop.
7. Send an invalid config directly (40 slots). Confirm 422, a field-level
   message, and that the stored document is unchanged.
8. Confirm the storefront is visually identical throughout. It should be — no
   theme reads any of this.

---

## 9. Blocker

`PUT` cannot succeed until the custom app has **write access to metafields**.
Current scopes are `read_products`, `read_inventory`, `read_locations`.

Everything else — the API, reads, validation, the registries, the console
wiring, the test suite — can be built and verified before that lands. The first
successful save is the only thing that waits.

Changing scopes may invalidate the current access token and require
re-approving the app. That breaks the pipeline until re-approved, not the
storefront. Confirm recovery by running `python -m scripts.fetch_locations`.

---

## 10. Out of scope

- `/api/analytics` — needs an event store. Phase 6/7.
- Publishing block lists to metafields — Phase 5. The pipeline keeps writing
  JSON to `backend/data/blocks/`.
- Any theme edit. Nothing here reaches a shopper.
- Postgres. The `db` service keeps running, unused. Left in compose rather than
  removed, because Phase 6 event storage is what it is for.

---

## 11. Open

- Does `wholesale-order-entry` have a per-person login worth adopting instead
  of the shared token?
- `config-contract.md` §12 asks whether `slots` belongs here or in the theme's
  own Online Store 2.0 section settings. If it moves, this API loses a field.
  Worth resolving before the theme work, not after.
- Should `GET` require the token too, once the VM's nginx configuration is
  known?
