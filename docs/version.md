# YMAL — versions

An in-house Shopify product-recommendation engine for Wooden Ships, built to
replace the Wiser AI app.

This file is shown on the console's Dashboard tab. Keep it readable by the web
team, not just by engineers.

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
