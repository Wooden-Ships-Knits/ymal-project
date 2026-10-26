# YMAL — versions

An in-house Shopify product-recommendation engine for Wooden Ships, built to
replace the Wiser AI app.

This file is shown on the console's Dashboard tab. Keep it readable by the web
team, not just by engineers.

---

## v1.3 — 2026-09-16

Three new places to be recommended something, and the end of Wiser's hold on
the cart.

### Inspired By Your Views

A second row on the product page, built from what the shopper has actually
been looking at rather than from the product in front of them: the top four
Featured products of each of their last five viewed products, minus everything
they have already seen or put in the cart. Shuffled once per visit, so the row
is the same on every page of that visit but different on the next one, and it
slides sideways like the YMAL row.

One colorway per style. Neighbouring products often recommend different shades
of the same sweater, and a shopper browsing football knits got a row that was
mostly one jersey.

It shows nothing at all to a first-time visitor, by design.

### Recently Viewed, in the cart drawer

Now one card at a time, swiped or stepped with the arrows, and it keeps up
with the cart: adding a product removes it from the row and pulls in the next,
whether it was added from the product page or from the row itself. Adding from
the row now also updates the cart total and the header count, which it did not
before.

### Recently Viewed, in checkout

Replaces the Wiser upsell block that sat in the order summary. Three products,
**oldest first** — by checkout, the recent ones are what the shopper just
decided against, so the sweater they looked at earlier is the one worth showing
again. It skips anything sold out, already in the order, or another colorway of
a style already in the order.

Checkout cannot see the shopper's browsing history: it runs sealed off from the
storefront. The list therefore travels on the cart itself, as the attribute
"YMAL viewed" — which is why product ids now appear in the order's Additional
details in the admin, beside the "YMAL block" marker that was already there.

Its views and clicks do NOT reach the Analytics tab yet. Purchases made from it
are still attributed.

### The cart drawer is the theme's again

The drawer shoppers saw belonged to Wiser, and any block we put in the theme's
own drawer was invisible to them. The theme's drawer was switched off, its cart
icon carried Wiser's marker, and Wiser's script caught the click. All three were
undone on the theme, and Wiser's app embed turned off with them, which also
removes its widgets, quick view and popup from that theme.

### Fixes worth naming

**The console lost Shopify access a day after every deploy.** The access token
lasts 24 hours and was fetched once at startup. It is now refreshed before it
expires, and a request that still comes back unauthorised is retried once with a
fresh token. The Ranking tab failing the morning after a deploy was this.

**Inspired By Your Views never appeared at all.** The row waits until the
shopper scrolls near it before loading, but it was watching itself to decide
that — and it stays hidden until it has cards to show. A hidden element is never
"near", so it waited forever.

**Add to cart was recorded for nothing.** Events from a page the list did not
recognise were dropped, and the page type was read from a value that was never
set, so everything arrived labelled "unknown".

### After updating

1. `git pull && docker compose up -d --build` on the VM, and change the nightly
   cron line from `pipeline` to `api`. Until then the dashboard rejects events
   from Inspired By Your Views.
2. Copy to the live theme: `assets/ymal-inspired.js`,
   `assets/ymal-recently-viewed.js`, `assets/ymal-recently-viewed-cart.js`,
   `snippets/ymal-recently-viewed-recorder.liquid`,
   `snippets/ymal-recently-viewed-cart.liquid`,
   `sections/ymal-inspired.liquid`, `templates/product.ymal-ibyv.liquid`,
   `templates/product.ymal-block.liquid`,
   `templates/product.ymal-card-compact.liquid`, and the recorder line in
   `layout/theme.liquid`.
3. Add the "YMAL Inspired By Your Views" section to the product template.
4. Checkout block: `npx shopify app deploy` then `release` from
   `~/ymal-checkout`, then add "YMAL Recently Viewed" in the checkout editor.
   See `checkout/README.md` — the app configuration ships with every deploy.

---

## v1.2 — 2026-09-12

### Tracking was installed and recorded nothing

Three separate faults, each enough on its own to lose every event. All three
failed silently: the block rendered, no error appeared anywhere, and the
Analytics tab read zero — which looks exactly like "nobody has clicked yet".

**The password.** The VM's nginx puts HTTP basic auth in front of
`ymal.pt-infashion.com` so the console is not public. That auth also covered
`/api/events`, and a shopper's browser has no password, so every beacon got a
401 before it reached us. Fixed in the VM's nginx, which is not part of this
repository — `frontend/storefront/install.md` now carries the exact block to
add and a command that proves it.

**One missing hyphen.** The list of sites allowed to send events named
`woodenships.com`. The shop is `wooden-ships.com`. The browser refused every
beacon before it left the page. This would still have blocked everything after
fixing the password.

**A race the beacon could lose.** Events were sent as `application/json`, which
obliges the browser to ask permission first. A beacon fired as someone leaves
the page loses that exchange often enough to matter. They now go as plain text,
which needs no permission step. The file says, in capitals, not to change it
back.

### The console now says when tracking is broken

A table of zeroes meant two completely different things — nobody has clicked
yet, or the endpoint refuses every event — and there was no way to tell them
apart. That, rather than any one of the faults above, is what let this go
unnoticed.

The Analytics tab now checks the real public address the way a shopper's
browser would, and says which of the two it is. When something is wrong it
names the cause and where the fix lives. The same check runs when the API
starts, so it also appears in the VM's logs.

### After updating

1. Add the nginx block from `install.md`, and reload nginx.
2. `git pull && docker compose up -d --build` on the VM.
3. Re-copy **two** theme files — `assets/ymal-track.js` and
   `sections/ymal-widget.liquid`. Both changed. `theme.liquid` is unchanged.
4. `docker compose run --rm api python -m scripts.nightly` to publish.
5. Click a recommendation, then open Analytics. A red banner names whatever is
   still wrong.

---

## v1.1 — 2026-09-12

### Ranking is now tunable from the console

A new **Ranking** tab. Sales weight, rare-tag sharpness and the six tag-facet
weights can be changed without a deploy, with a live preview that re-ranks a
real product as you move a slider. Nothing reaches the storefront until you
press **Rebuild and publish**.

What stayed in code, deliberately: the eligibility rule and the season filter.
Those decide *whether* a product may be shown, and a wrong value there puts a
markdown or out-of-season product in front of a shopper — a different kind of
mistake from a badly-sorted row.

### Sales are counted per style, not per colorway

A recommendation row shows one product per style, so the sales figure behind it
now sums every colorway of that style. Previously a sweater selling 38 units
across twelve colorways was ranked as though it had sold 9. On this catalog 18
of 128 styles were understated by 2x or more.

The 0–1 scale was also wrong. It was anchored to the highest single row in the
sales table — which turned out to be a product that is not even active (499
units), with "Front & Back Placement Add-on", a service line, in third place at
119. Every real garment was being divided by a number no shopper can buy, which
squashed the whole column into the bottom third of its range. The scale is now
set by the best-selling style that can actually appear in a recommendation.

Side effect worth knowing: styles with many colorways gained. KEY WEST CREW
CHUNKY COTTON now appears in 83 of 261 top-sixes, up from 54. If that feels too
strong, lower **Sales volume** on the Ranking tab.

### Fixes

- **The nightly job was publishing last month's settings.** The pipeline ran in
  its own container image, and `docker compose up -d --build` does not rebuild
  services outside the default profile — so it silently kept the code it was
  first built with. Top Selling was published on a 90-day window for a day
  after the window became 14. That service is gone; pipeline work now runs in
  the `api` container, which every deploy rebuilds.
- **The console described Top Selling as "the last 90 days"** after it became
  14. Those descriptions are now generated from the settings themselves.
- **Tracking never ran.** The block's script executed while the page was still
  parsing, before the deferred `ymal-track.js` had defined anything, so it quit
  immediately. No impressions, no clicks — and no purchase attribution either,
  because the cart attribute is written by the same code. Silently, with the
  block rendering perfectly.
- **`install.md` told the theme to overwrite `product-list.liquid`** with a file
  that contains no YMAL code. Following it would have reverted a live section.

### Tools

`solver/addtags.py` applies a set of tags across every colorway of a named
style. Dry run by default; it can add a tag but never remove one. Used to fix
the PUMPKIN FAIR ISLE recommendations, where the anchor had no `fair isle` tag
and the pumpkin products were missing the halloween cluster the ghost sweaters
all carried.

---

## v1.0 — 2026-09-11

The first complete version: everything needed to replace Wiser, though the
switch itself had not been made.

### The nightly pipeline

Seven steps, stopping on the first failure so a half-finished chain never
publishes:

| Step | What it does |
|---|---|
| `fetch_products` | the eligible catalog — active, not `*SALE*`, and replenishable at Bali To Produce rather than fixed stock |
| `build_features` | tags, collections, season and price band per product |
| `build_blocks` | Trending, Top Selling and New Arrivals |
| `build_pools` | content similarity per product — rare tags weighted far above common ones, one product per style, season as a hard filter |
| `build_copurchase` | reranks on what actually sold together |
| `publish_all` | writes the lists to Shopify metafields |
| `attribute_orders` | credits orders to the block that led to them |

Lists are stored as product references, so Liquid receives live product objects
— today's price and today's stock, from a list written overnight.

### The storefront block

One theme section, which is the theme's own product list plus a **Products
from** setting. A YMAL row therefore looks exactly like every other product row
on the site, and keeps looking like one when the theme changes.

Eligibility is re-checked in Liquid on every request and **fails closed**: a
product with no eligibility flag is not shown. The nightly job decides who is a
*candidate*; the theme decides who may actually be *shown*. That split is the
thing Wiser got wrong — their lists could show a product that had since gone on
sale or out of stock.

### The console

Manual Update, Analytics, and Exclude Products.

### Tracking

Impressions, clicks, add-to-cart, and purchases. Purchase attribution works by
writing a cart attribute when a shopper clicks a recommendation; Shopify
carries it through checkout onto the order, so there is no webhook and nothing
on the thank-you page. Last touch — it credits the last block clicked before
checkout, which is a correlation and not a claim that the block caused the sale.

No personal data. The session id is random, lives in the tab, and is sent
nowhere else.

### Not in v1.0

Recently Viewed was written but not installed on the theme. The checkout
extension, the A/B test against Wiser, and the machine-learning ranking upgrade
were not started.

Wiser was still the live recommender on the published theme.
