# YMAL — Theme (storefront)

What the shopper sees. Liquid snippets plus a small amount of JavaScript.

## Status

**Not started.** This folder is scaffolding.

## The one idea that matters

The theme is edited **once**. After that, every change to what appears where is
made in the console, not here.

A single snippet reads the `ymal.config` metafield, looks up the blocks
configured for the current page template, and renders each one. Adding a block
to the homepage becomes a checkbox in the console — not a theme edit, a preview
and a publish.

See `docs/config-contract.md` for the exact shape of what it reads.

## Planned contents

```
theme/
├── snippets/
│   ├── ymal.liquid              the universal block renderer
│   └── ymal-card.liquid         one card — delegates to the theme's own card
├── assets/
│   ├── ymal-recently-viewed.js  localStorage read/write + render
│   └── ymal-events.js           impression / click / add-to-cart events
└── install.md                   which template gets which render tag
```

## Install (one line per template)

```liquid
{% render 'ymal', page_type: 'product', product: product %}
{% render 'ymal', page_type: 'home' %}
{% render 'ymal', page_type: 'cart' %}
```

## What the snippet does

1. Stop immediately if `config.enabled` is false — the kill switch.
2. Read `placements[page_type]`. Nothing configured for this page → render nothing.
3. For each configured block, resolve its list:
   - `trending`, `top_selling`, `new_arrivals` → shop metafield
   - `featured` → this product's metafield
   - `recently_viewed` → client-side, from localStorage
4. Skip the anchor product, and anything where `item.available` is false.
5. Render up to `slots` cards using the theme's existing product card.
6. Render nothing at all — no heading — if a block comes back empty.

Step 4 is the important one. The nightly job decides which products are
candidates; the theme decides whether each one may still be shown *right now*.
That split is what Wiser got wrong.

## Recently Viewed

No backend, no data of ours, no login. On each product page a few lines of JS
append `{handle, id, ts}` to `localStorage`, and the block reads that list back.

It is per browser by nature — the same person on a phone and a laptop has two
different lists — and empty in a fresh or private browser, where the block must
hide itself rather than show an empty heading.

## Constraints

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
it. Without those, the console's analytics screen has nothing to report.

| Event | Fires when |
|---|---|
| `ymal_impression` | block enters the viewport (IntersectionObserver, once per pageview) |
| `ymal_click` | a card is clicked (delegated from the container) |
| `ymal_atc` | add-to-cart on a product that came from a block |

The holdout flag rides on these events too — see `docs/ymal-flow.drawio` page 7.
It has to be switched on with the first block that ships; it cannot be applied
retroactively.
