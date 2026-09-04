# YMAL — Frontend

Two things live here, both of them JavaScript:

1. **The console** — the admin page the web team uses to decide which
   recommendation blocks appear on which page, and to see what each one earns.
   Modelled on Wiser's "Active Widgets" screen.
2. **The storefront** — the Liquid snippet and the small amount of JS that run
   on wooden-ships.com and render the blocks to shoppers.

## Status

**Not started.** This folder is scaffolding — the structure is settled so that
work can start, not because there is code in it yet.

---

## Stack

Follows `wholesale-order-entry`, which is the closest sibling project: same
team, same shape of problem, already deployed this way.

| Layer | Choice |
|---|---|
| UI | React 18 + Vite |
| Routing | **None.** Tabs are `useState` plus a `TABS` array, exactly as `wholesale-order-entry/frontend/src/admin/AdminApp.jsx` does it |
| API calls | Plain `fetch` in a per-feature `api.js` |
| Backend | FastAPI in `backend/`, which is the only thing holding Shopify credentials |
| Deploy | Own `Dockerfile` + `nginx.conf` in this folder, serving the built static files |

No router library and no component framework. The console is roughly four
screens; a route table would be more machinery than the problem needs, and the
sibling project proves the pattern holds at a larger size than this.

---

## Folder hierarchy

Mirrors `wholesale-order-entry/frontend/`: a folder per feature holding that
feature's screens **and its own `api.js`**, with shared pieces in `components/`
and pure helpers in `lib/`.

```
frontend/
├── index.html                  Vite's entry point: <div id="root"> + the main.jsx
│                               script tag. Required at the root, rarely edited.
├── package.json
├── vite.config.js
├── Dockerfile                  build the static bundle, serve it with nginx
├── nginx.conf
├── .env.example                VITE_API_BASE — never a Shopify credential
├── public/                     favicon, logo
└── src/
    ├── main.jsx                mount point — imports index.css, renders App
    ├── App.jsx                 the shell: sidebar, header, tab state
    ├── api.js                  shared fetch wrapper + error handling
    ├── index.css               the stylesheet (this is the CSS one)
    │
    ├── setup/                  TAB — Setup Widgets
    │   ├── SetupWidgets.jsx        the grid of page-template cards
    │   ├── PageTemplateCard.jsx    one card: name, enabled blocks, Setup button
    │   ├── SetupPanel.jsx          the editor: blocks, order, slots, heading
    │   └── api.js                  GET/PUT /api/config, POST /api/config/undo
    │
    ├── analytics/              TAB — Analytics
    │   ├── Analytics.jsx           per block and per page
    │   ├── BlockTable.jsx          impressions, clicks, CTR, attributed revenue
    │   └── api.js
    │
    ├── exclude/                TAB — Exclude Products
    │   ├── ExcludeProducts.jsx     the merchandiser block list
    │   └── api.js
    │
    ├── components/             shared across tabs
    │   ├── Sidebar.jsx
    │   ├── Header.jsx
    │   ├── BlockChip.jsx           the pill on a page-template card
    │   ├── Toggle.jsx
    │   └── Modal.jsx
    │
    └── lib/                    pure functions, no fetch, no JSX
        ├── blocks.js               the five block IDs, labels, defaults
        ├── pageTemplates.js        the nine page templates
        └── validateConfig.js       mirrors the backend rules, for instant feedback
```

### Adding a tab

One folder, one entry in the `TABS` array in `App.jsx`, one conditional render.
That is the whole ceremony — same as `AdminApp.jsx` in the sibling project.

### Tabs vs pages

`wholesale-order-entry` uses two different patterns and it is worth copying the
distinction rather than the code:

- **Pages get a path.** `main.jsx` picks a component from a `PAGES` map keyed on
  `window.location.pathname` — `/order_form`, `/admin`, `/reps`. Still no router
  library, just an object lookup.
- **Tabs inside a page get `useState`.** `AdminApp.jsx` holds `tab` in state and
  conditionally renders.

The console is one page with tabs, so it starts with the second pattern. If the
web team ever wants to link someone straight to Analytics, promote the tabs to
paths using the first.

---

## The storefront half

The Liquid snippet and the script that runs on the live store. Not part of the
Vite build — these files are copied into the Shopify theme.

```
frontend/storefront/
├── snippets/
│   ├── ymal.liquid                 the universal block renderer
│   └── ymal-card.liquid            one card — delegates to the theme's own card
├── assets/
│   ├── ymal-recently-viewed.js     localStorage read/write + render
│   └── ymal-events.js              impression / click / add-to-cart
└── install.md                      which theme template gets which render tag
```

### The one idea that matters

**The theme is edited once.** After that, every change to what appears where is
made in the console, not here.

The snippet reads the `ymal.config` metafield, looks up the blocks configured
for the current page template, and renders each one. Adding a block to the
homepage becomes a checkbox — not a theme edit, a preview and a publish.

See `docs/config-contract.md` for the exact shape of what it reads.

### What the snippet does

1. Stop immediately if `config.enabled` is false — the kill switch.
2. Read `placements[page_type]`. Nothing configured → render nothing.
3. For each configured block, resolve its list:
   - `trending`, `top_selling`, `new_arrivals` → shop metafield
   - `featured` → this product's metafield
   - `recently_viewed` → client-side, from localStorage
4. Skip the anchor product, and anything where `item.available` is false.
5. Render up to `slots` cards using the theme's existing product card.
6. Render nothing at all — no heading — if a block comes back empty.

Step 4 is the important one. The nightly job decides which products are
*candidates*; the theme decides whether each one may be shown *right now*. That
split is what Wiser got wrong.

### Recently Viewed

No backend, no data of ours, no login. A few lines of JS append
`{handle, id, ts}` to `localStorage` on each product page, and the block reads
that list back.

Per browser by nature — the same person on a phone and a laptop has two
different lists — and empty in a fresh or private browser, where the block must
hide itself rather than show an empty heading.

---

## Storefront constraints

- Reuse the theme's existing product card. It must look native, not bolted on.
- No layout shift — fixed aspect-ratio image containers.
- Empty block renders nothing, never a heading with no products.
- Real `<a>` links, alt text, keyboard navigable.
- Mobile-first: carousel on mobile, grid on desktop. Confirm against the theme.
- Back up the theme, work on a copy, preview, then publish. Non-negotiable on a
  live store.
- Kill switch: `config.enabled = false` hides everything without a deploy.

## Events

Every event carries the **block name** and the **page template** that produced
it. Without those, the Analytics tab has nothing to report.

| Event | Fires when |
|---|---|
| `ymal_impression` | block enters the viewport (IntersectionObserver, once per pageview) |
| `ymal_click` | a card is clicked (delegated from the container) |
| `ymal_atc` | add-to-cart on a product that came from a block |

The holdout flag rides on these events too. It has to be switched on with the
first block that ships — it cannot be applied retroactively.

---

## Security

**Shopify credentials never reach the browser.** The console calls the FastAPI
backend; the backend talks to Shopify using the existing `ymal.auth` token
exchange. The only thing in `.env` here is `VITE_API_BASE`.

## The rule that governs the console

**It writes `ymal.config` and nothing else.** It does not compute
recommendations, does not write product data, and is never in the path of a
storefront request. If the console is down, the storefront is unaffected.

A malformed config would silently blank every block, so the backend validates
before writing and keeps the previous version for one-click undo. `lib/validateConfig.js`
mirrors those rules client-side for instant feedback — it does not replace them.
