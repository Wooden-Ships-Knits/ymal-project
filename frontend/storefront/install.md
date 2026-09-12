# Installing YMAL on the theme

The web team adds a YMAL block the same way they add a Wiser one: in the theme
editor, from the block list. Wiser's appear under **Apps** because Wiser is an
installed app shipping theme app extensions. YMAL's are theme sections, so they
appear under **Sections** instead. Same drag, same settings panel, no app to
install or host.

**Back up the theme first.** Duplicate it, work on the copy, preview, publish.
Non-negotiable on a live store.

---

## 1. Run the publish job first

The card template fails closed: a product with no `ymal.eligible` metafield
does not render. Install before publishing and every block will be empty.

```bash
cd backend
.venv/bin/python -m scripts.publish_all --dry-run
.venv/bin/python -m scripts.publish_all
```

## 2. Which files to copy, and which NOT to

`ymal-widget.liquid` IS the theme's own `product-list` section, copied and
given one extra setting - **Products from**. Same slider, same aspect-ratio
handling, same quick buy, same `product-block`, so a YMAL row looks like every
other product row on the site. It is installed under a new name rather than
over the original, so the theme keeps a working `product-list` either way.

### Safe: new files, nothing in the theme shares these names

| File | Needed for |
|---|---|
| `sections/ymal-widget.liquid` | every block except Recently Viewed |
| `snippets/ymal-card.liquid` | the card used inside that section |
| `snippets/ymal-recently-viewed.liquid` | Recently Viewed on a product or home page |
| `snippets/ymal-recently-viewed-cart.liquid` | Recently Viewed in the cart drawer |
| `templates/product.ymal-card.liquid` | Recently Viewed card fetch |
| `templates/product.ymal-card-compact.liquid` | Recently Viewed card in the cart drawer |
| `assets/ymal-recently-viewed.js` | Recently Viewed |
| `assets/ymal-recently-viewed-cart.js` | Recently Viewed in the cart drawer |
| `assets/ymal-track.js` | analytics AND purchase attribution |

### DO NOT copy: `sections/product-list.liquid`

That file is the theme's ORIGINAL section, reconstructed and kept here only so
the YMAL version can be diffed against it. It contains no YMAL code at all.
Copying it over the theme reverts that section to the day it was reconstructed
and silently discards anything the web team has changed since.

Install `ymal-widget.liquid` instead. If you ever do want the setting on the
real `product-list` section, diff the two files and apply the difference by
hand - do not overwrite.

### Hand-edit, do not overwrite: `sections/cart-drawer.liquid`

The copy here is the theme's own cart drawer plus a three-line insertion. The
theme's version moves; this one does not. Paste the insertion rather than the
file, after the cross-sells block:

```liquid
<div class="cart-drawer__content-item">
  {%- render 'ymal-recently-viewed-cart', slots: 3 -%}
</div>
```

### Hand-edit: `layout/theme.liquid`

```liquid
<script src="{{ 'ymal-track.js' | asset_url }}" defer></script>
```

Anywhere in `<head>` is fine, and `defer` is correct - it must NOT be dropped
to force ordering. The section's own inline script waits for DOMContentLoaded
precisely so that a deferred track script has already run by the time it looks
for `window.ymalTrack`. Loading it without `defer` also works but blocks
parsing for no benefit.

Without this there is no analytics AND no purchase attribution. The block
script starts with `if (typeof window.ymalTrack !== "function") return;`, so a
missing tag also skips the `/cart/update.js` call that writes the `YMAL block`
cart attribute - the thing `attribute_orders` reads back off orders. It fails
silently, with no console error and no empty state; the Analytics tab simply
stays at zero.

Recently Viewed is not a `Products from` option: it has no metafield to read,
so it renders client-side from the shopper's browser and needs its own snippet.

## 4. Add blocks in the theme editor

Open the theme editor, pick a template, **Add section** -> **YMAL
Recommendations**. Then set:

| Setting | Notes |
|---|---|
| Block | Featured needs a product to be about, so it only works on a product page |
| Heading | The web team's words |
| Products to show | 2-12. Fewer may appear once the gate has run |
| Columns on desktop | 2-6. Phones always show one scrolling row |
| Layout | Carousel with arrows, or a grid that wraps |
| Full width | Edge to edge, matching the app blocks already on this store |
| Page type | Used for tracking, so Analytics can group by page |

Add the section more than once for more than one block on a page.

---

## What to check before publishing

1. **Preview, do not publish.** The theme editor previews on the live store
   without affecting shoppers.
2. **No `*SALE*` product appears in any block.** Search a block's rendered
   products for the marker. One appearing means the gate is broken.
3. **No fixed-stock product appears.** Cross-check a few against
   `backend/data/phase1/active_products.csv` - anything with `eligible` false
   must not be on screen.
4. **A block with nothing to show renders nothing** - no stray heading.
5. **Recently Viewed:** open a product page, see nothing (one view, and it is
   the anchor); open a second, the first appears; open a third, two appear.
6. **Private window:** Recently Viewed should be absent, not empty.

## Matching the existing app blocks

The Wiser blocks on this store are full-bleed carousels, four across. To match:

| Setting | Value |
|---|---|
| Layout | Carousel with arrows |
| Full width | ticked |
| Card width | 236px |
| Gap between columns | 20px |
| Heading size | 40px, Light, Centre |

Those numbers are read off the app block's own rendered markup, not guessed.

The **Choose Option** button on each card is not ours - it comes from the
theme's `product-block`, which draws it when Theme settings -> quick buy style
is set to "button". If the button is missing from YMAL cards it is missing from
the theme's own product grids too, and the fix is that setting rather than
anything here.

What is deliberately NOT copied: the app's CSS class names. Reusing them would
match for free, but that styling ships with the app and disappears the day it
is uninstalled - which is the plan at Phase 7.

The arrows only appear when the row actually overflows - a block showing four
of four products needs none, and a dead arrow reads as broken. The row scrolls
by swipe and trackpad regardless, so it still works if the script never runs.

## The kill switch

Delete the section in the theme editor, or toggle its visibility. There is no
deploy involved either way.

For a store-wide stop without touching the theme, unpublish the metafields:
every block except Recently Viewed then renders nothing, because the gate fails
closed.

## Where each block's list comes from

| Block | Source |
|---|---|
| Featured | `product.metafields.ymal.featured` - this product's own pool |
| Trending | `shop.metafields.ymal.trending` |
| Top Selling | `shop.metafields.ymal.top_selling` |
| New Arrivals | `shop.metafields.ymal.new_arrivals` |
| Recently Viewed | the shopper's browser, no metafield at all |

All four metafields are `list.product_reference`, so Liquid receives the live
product object - a list written at 03:00 renders today's price at noon, and a
product that sold out in between renders nothing.

## Recently Viewed, specifically

Ships on its own. No backend, no metafields, no config - the one block that can
go live before anything else exists.

It stores `{handle, id, ts}` for twenty products in `localStorage` and nothing
else, and never leaves the device. Title, price, image and availability are
fetched fresh from the theme on every render, so a handle stored three weeks
ago still shows today's price.

Per browser by nature: the same person on a phone and a laptop has two
different lists. Every store works this way, Wiser almost certainly included.

| Situation | What happens |
|---|---|
| No history yet | Section stays hidden. No empty heading. |
| Private browsing / storage blocked | The storage call throws, is caught, and the block never unhides. |
| Product sold out, on `*SALE*`, or fixed stock | The gate rejects it, the script skips it. |
| Product deleted or handle renamed | The fetch fails, the script skips it. |
| Nothing survives | Section stays hidden. |

## Tracking

Copy `assets/ymal-track.js` into the theme and load it once, in
`layout/theme.liquid` before `</head>`:

```liquid
<script src="{{ 'ymal-track.js' | asset_url }}" defer></script>
```

It defines `window.ymalTrack`, which the block scripts already call and which
does nothing when absent - so blocks can ship before tracking, and tracking can
be removed without touching them.

**This data cannot be collected retroactively.** Whatever is not captured from
the first day is gone, and it is what the Phase 8 ranking model trains on.

What is recorded: which block, which page, which product, its position in the
row, and a random session id the browser generates for itself. No cookie, no
identifier that outlives the tab, nothing traceable to a person.

### The endpoint must be reachable WITHOUT the console's password

This is the step that was missed on 2026-09-12, and it recorded nothing for as
long as it went unnoticed. The VM's nginx puts HTTP basic auth in front of
`ymal.pt-infashion.com` so the console is not public. That auth also covered
`/api/events`, and a shopper's browser has no password - so every beacon got a
401 before it ever reached the API. Nothing failed visibly: the block rendered,
the console showed no error, and Analytics simply stayed at zero.

Add an exact-match location to the VM's nginx server block. `location =` has
higher priority than a prefix match, so it wins wherever it is placed:

```nginx
location = /api/events {
    auth_basic off;
    proxy_pass http://127.0.0.1:8083;
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Then `sudo nginx -t && sudo systemctl reload nginx`.

Everything else stays behind the password. This is the only unauthenticated
write in the project: the endpoint validates every event against a fixed shape
and reduces it to known columns before storage, precisely so that being open
costs nothing more than junk rows. Adding `limit_req` in front of it is
reasonable if that ever becomes a problem.

Check it from a machine that has never seen the password:

```bash
curl -i -X POST https://ymal.pt-infashion.com/api/events \
  -H 'Content-Type: text/plain' \
  -d '{"events":[]}'
```

**202 is correct. 401 means the location block is missing or not reloaded.**

### The beacon sends text/plain, and must keep doing so

`ymal-track.js` sends JSON with `Content-Type: text/plain`. That looks wrong and
is deliberate: `application/json` is not on the CORS safelist, so the browser
must send a preflight `OPTIONS` first, and a beacon fired while the page is
unloading loses that race often enough to matter. `text/plain` keeps it a simple
request with no preflight. The API parses the body by hand and ignores the
header.

### The CORS allowlist must name the real domain

`YMAL_STOREFRONT_ORIGINS` in `.env`, or the default in `app/main.py`. It said
`woodenships.com` for a while; the shop is `wooden-ships.com`, **with a
hyphen**, and one missing character was enough for the browser to refuse every
beacon. It is not a wildcard on purpose - otherwise any page on the internet
could post events into this shop's analytics.

Purchases work differently. Clicking a product in a YMAL row writes a cart
attribute naming the block; Shopify carries that through checkout onto the
order, and `scripts/attribute_orders.py` reads it back from orders the pipeline
already fetches. No webhook, no session-to-order join, and nothing on the
thank-you page, which Shopify restricts.

The attribute is visible to the shopper on their own order, which is why it
reads `YMAL block: trending` rather than an internal id.

Attribution is last touch - whichever block was clicked most recently before
checkout. It is not a claim that the block caused the sale; the honest number
for that is the Phase 7 holdout.

### Old notes

The script calls `window.ymalTrack(name, detail)` if it exists and does nothing
if it does not, so blocks can ship before the events module does and start
reporting the moment it lands.

Events carry `block` and the page type. Without those two fields the Analytics
tab has nothing to group by.
