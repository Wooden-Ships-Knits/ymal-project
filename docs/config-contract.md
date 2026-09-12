# YMAL — The Config Contract

**Created 2026-09-04.** The agreement between the three layers.

This is the keystone of the project. The console writes it, the theme reads it,
the pipeline never touches it. Getting it right is what lets the web team
re-arrange the storefront without an engineer and without a deploy — which is
the entire reason Wiser's "Active Widgets" screen is worth copying.

Design it before writing any of the three layers, because all three have to
agree on it.

---

## 1. What problem this solves

Today, changing what appears on a product page means editing Liquid, previewing,
and publishing — engineering, every time.

With this contract, the theme is edited **once**. It learns to read a settings
document and render whatever that document says. After that:

| Task | Before | After |
|---|---|---|
| Put Trending on the homepage | edit theme → preview → publish | tick a box, save |
| Reorder two blocks | edit theme → preview → publish | drag, save |
| Turn off a block that is not earning | edit theme → preview → publish | untick, save |
| Turn everything off in an emergency | edit theme → publish | one switch |

---

## 2. Every metafield in the system

Shopify metafields are storage slots attached to a resource. Liquid can read
them at render time.

| Owner | Namespace | Key | Type | Written by | Read by |
|---|---|---|---|---|---|
| shop | `ymal` | `config` | `json` | console | theme |
| shop | `ymal` | `config_previous` | `json` | console | undo only |
| shop | `ymal` | `trending` | `list.product_reference` | pipeline | theme |
| shop | `ymal` | `top_selling` | `list.product_reference` | pipeline | theme |
| shop | `ymal` | `new_arrivals` | `list.product_reference` | pipeline | theme |
| product | `ymal` | `featured` | `list.product_reference` | pipeline | theme |

`recently_viewed` has no metafield. It lives in the shopper's browser.

### Why `list.product_reference` and not our own JSON

A product reference hands Liquid the **live product object** — current title,
price, image, and `available`. Store our own copy of that data instead and a
list written at 03:00 renders yesterday's price at noon.

It also means the pipeline never needs to fetch `featuredImage` or
`priceRangeV2` at all.

> **VERIFIED 2026-09-08.** A *shop-level* `list.product_reference` metafield
> does resolve to product objects, exactly as a product-level one does.
> Confirmed against the live shop: `shop.metafields.ymal.trending` returns real
> products with titles, and `product.metafields.ymal.featured` does the same.
> The `json`-metafield fallback is not needed.

---

## 3. The `ymal.config` document

```json
{
  "version": 1,
  "enabled": true,
  "updated_at": "2026-09-04T09:12:00Z",
  "updated_by": "web-team",
  "placements": {
    "product": [
      { "block": "featured",        "heading": "You May Also Like", "slots": 6, "enabled": true },
      { "block": "trending",        "heading": "Trending Now",      "slots": 6, "enabled": true },
      { "block": "recently_viewed", "heading": "Recently Viewed",   "slots": 4, "enabled": true }
    ],
    "home": [
      { "block": "trending",        "heading": "Trending Now",      "slots": 8, "enabled": true },
      { "block": "new_arrivals",    "heading": "New Arrivals",      "slots": 8, "enabled": true }
    ],
    "cart": [
      { "block": "recently_viewed", "heading": "Recently Viewed",   "slots": 4, "enabled": true }
    ]
  }
}
```

**Order in the array is the order on the page.** A page template absent from
`placements` renders nothing — which is also how you remove blocks from a page.

| Field | Meaning |
|---|---|
| `version` | Schema version. The theme refuses a config it does not understand rather than half-rendering one. |
| `enabled` | Global kill switch. `false` renders nothing anywhere, with no deploy. |
| `updated_at` / `updated_by` | Written by the console. Answers "who changed the homepage" without a git log. |
| `block` | One of the block IDs in §4. |
| `heading` | The text above the block. The web team's words, not ours. |
| `slots` | How many products to show. |
| `enabled` | Per-block switch — keeps a block's configuration while turning it off. |

---

## 4. Block registry

Five blocks. `requires_anchor` means the block needs a product to be "about".

| ID | Label | Requires anchor | Source |
|---|---|---|---|
| `featured` | Featured Products | yes | tag similarity to the anchor |
| `trending` | Trending Products | no | orders, last 14 days, by quantity |
| `top_selling` | Top Selling | no | orders, last 14 days, by quantity |
| `new_arrivals` | New Arrivals | no | `publishedAt` within 30 days |
| `recently_viewed` | Recently Viewed | no | the shopper's own browser |

### Which block is allowed on which page

The console must grey out combinations that cannot work, rather than letting
someone configure a block that will silently render nothing.

| Page template | featured | trending | top_selling | new_arrivals | recently_viewed |
|---|---|---|---|---|---|
| `product` | yes | yes | yes | yes | yes |
| `home` | no | yes | yes | yes | yes |
| `cart` | see note | yes | yes | yes | yes |
| `collection` | no | yes | yes | yes | yes |
| `search` | no | yes | yes | yes | yes |
| `not_found` | no | yes | yes | yes | yes |
| `blog` | no | yes | yes | yes | yes |
| `account` | no | yes | yes | yes | yes |
| `thank_you` | see note | yes | yes | yes | yes |

**Note on `cart` and `thank_you`:** `featured` is possible there only if the
anchor is derived from the cart contents or the ordered items. That is a design
decision with its own rules (which item is the anchor when there are four?), not
a free extension. Left out of v1.

**Note on `thank_you`:** Shopify restricts what can be injected into the
thank-you and order status pages, and the rules differ by plan and checkout
version. Verify what this store can actually do before offering that card.

---

## 5. Page templates

A fixed list. Adding one later is a change to this document and to the theme —
not to the schema.

```
product  home  cart  collection  search  not_found  blog  account  thank_you
```

**v1 ships `product` and `home` only.** They cover most of the traffic and both
are cheap. The config describes all nine from the start so that widening later
is configuration rather than a migration.

---

## 6. Validation

A malformed config silently blanks every block, and nobody notices until traffic
drops. The console validates **before** writing, and rejects rather than repairs.

| Rule | Reason |
|---|---|
| `version` is an integer the theme knows | a newer config must not half-render on an older theme |
| `enabled` is a boolean | the kill switch must be unambiguous |
| `placements` keys come from the page template list | a typo would be a page that never renders |
| each entry's `block` is a known block ID | same |
| the block is allowed on that page template (§4) | prevents configuring a block that cannot work |
| `heading` is a string, 1–60 characters | longer breaks the layout |
| `slots` is an integer, 2–12 | zero is meaningless; 40 is a wall of products |
| no duplicate `block` within one page template | two Trending rows on one page is always a mistake |
| at most 4 blocks per page template | a page of nothing but recommendations sells nothing |
| no unknown fields | strict rejection beats silent ignoring |

---

## 7. Versioning and undo

On every successful write, the console copies the current `ymal.config` to
`ymal.config_previous` first. Undo is one click, not a restore.

`version` exists so the theme can refuse a document it does not understand. The
theme is the slowest layer to change — it needs a preview and a publish — so the
config format has to be able to move ahead of it safely.

---

## 8. What the theme does with it

One line per template:

```liquid
{% render 'ymal', page_type: 'product', product: product %}
{% render 'ymal', page_type: 'home' %}
```

Inside the snippet:

```liquid
{%- assign cfg = shop.metafields.ymal.config.value -%}
{%- if cfg.enabled -%}
  {%- assign blocks = cfg.placements[page_type] -%}
  {%- for b in blocks -%}
    {%- if b.enabled -%}
      {%- case b.block -%}
        {%- when 'trending' -%}
          {%- assign items = shop.metafields.ymal.trending.value -%}
        {%- when 'top_selling' -%}
          {%- assign items = shop.metafields.ymal.top_selling.value -%}
        {%- when 'new_arrivals' -%}
          {%- assign items = shop.metafields.ymal.new_arrivals.value -%}
        {%- when 'featured' -%}
          {%- assign items = product.metafields.ymal.featured.value -%}
        {%- when 'recently_viewed' -%}
          {%- comment -%} rendered client-side from localStorage {%- endcomment -%}
      {%- endcase -%}
      ...filter, then render up to b.slots cards...
    {%- endif -%}
  {%- endfor -%}
{%- endif -%}
```

Then, for every item, the theme still checks live state:

- skip the anchor product itself
- skip anything where `item.available` is false
- stop at `b.slots`
- if nothing survives, render **nothing** — no empty heading

The nightly job decides which products are *candidates*. The theme decides
whether each one may be shown *right now*. That split is what Wiser got wrong,
and it survives every other change to this project.

---

## 9. The console API

The JS frontend talks only to these. **Shopify credentials never reach the
browser** — the page calls our API, our API calls Shopify.

```
GET  /api/config
     -> { "config": { ... }, "has_previous": true }

PUT  /api/config
     body: the config document
     -> 200 { "ok": true, "version": 1, "updated_at": "..." }
     -> 422 { "errors": [ { "path": "placements.product[1].slots",
                            "message": "must be between 2 and 12" } ] }

POST /api/config/undo
     -> restores ymal.config_previous

GET  /api/blocks
     -> [ { "id": "featured", "label": "Featured Products",
            "requires_anchor": true,
            "supported_page_templates": ["product"],
            "default_heading": "You May Also Like", "default_slots": 6,
            "list_published": true } ]

GET  /api/page-templates
     -> [ { "id": "product", "label": "Product Page", "live": true }, ... ]

GET  /api/analytics?from=&to=
     -> per block and page template, once the event store exists
```

`list_published` on `/api/blocks` lets the console warn honestly: *"Trending is
enabled on 2 pages but no list has been published yet."* A block configured but
unpublished renders nothing, and that should be visible in the console rather
than discovered on the storefront.

---

## 10. The line between the console and the code

The original version of this section said every scoring knob stayed in
`settings.py`, "owned by engineering", and that we should revisit once the team
had used the console for a while. That happened on 2026-09-12: the web team
asked for the ranking weights, having been told four times in a week to change a
number in Python and wait for a deploy.

### In the config, editable from the console

The `tuning` block — see §10.1. All of it changes only the **order** of a row:

- `popularity_weight` — how much sales volume may lift a product within a pool
- `idf_power` — how sharply rare tags are favoured over common ones
- `weights` — the six facet weights: motif, fabric, colour, silhouette,
  collection, other

The worst a bad value here can do is produce a badly-ordered row.

### Still in `backend/ymal/settings.py`

- **the eligibility rule** — the Bali location pattern, the `*SALE*` marker
- **`REQUIRE_SAME_SEASON`** and the seasonless fallback
- the Trending / Top Selling / New Arrivals windows
- stored list depth, and the near-universal-collection cutoff

The split is not "simple vs complex". It is that everything above decides
**whether** a product may be shown, and a wrong value puts a markdown or
out-of-season product in front of a shopper. That is a different class of
mistake from an ugly row, and not one a slider should be able to make.

The windows stay for a narrower reason: Shopify silently truncates order history
past 60 days, so a window set beyond it returns less data than it claims and
looks perfectly healthy. Until the pipeline detects and reports that, the number
should not be a slider.

### 10.1 The tuning block

```json
"tuning": {
  "popularity_weight": 0.4,
  "idf_power": 2.0,
  "weights": {
    "motif": 3.0, "fabric": 2.0, "colour": 1.5,
    "silhouette": 1.5, "collection": 1.5, "other": 2.0
  }
}
```

Every field is optional, and **the whole block is optional** — absent means "use
the `settings.py` defaults", which is what every config written before
2026-09-12 says. `weights` merges per facet, so sending only `motif` leaves the
other five alone.

Ranges are defined once, in `ymal/tuning.py`, and enforced by
`config_schema.validate` like everything else here: **rejected, not clamped**. A
clamped value would leave the console displaying a number the pipeline is not
using, which is exactly the bug that had Top Selling described as 90 days while
computing 14.

One rule is not a range: at least one facet weight must be above zero. All six at
zero scores every candidate at zero, `build_pool` drops candidates scoring zero,
and every pool in the shop comes out empty — a symptom that gives no hint of its
cause.

### 10.2 How it reaches the pipeline

`ymal/tuning.py` reads the block and assigns to the `settings` module at the
start of `build_pools`. That is blunt, and it works only because every consumer
reads `settings.POPULARITY_WEIGHT` at call time rather than copying it into a
local at import. **If you ever change that, this breaks silently.**

`apply()` always starts from the defaults, so a key the console removes returns
to its `settings.py` value rather than keeping the last run's number. This
matters because the api container is long-lived and also serves preview requests
with arbitrary tunings.

Shopify being unreachable is not fatal: the run proceeds on the `settings.py`
defaults and says so. A pipeline that refused to build because a settings
document could not be read would be worse than one that builds with the values
in the code.

### 10.3 Saving is not publishing

`PUT /api/tuning` stores numbers. Nothing reaches a shopper until the pipeline
runs — either the nightly job, or **Rebuild and publish** in the console, which
is the same `/api/run` Manual Update uses. They are two actions on purpose:
tying them together would mean fiddling with a slider fired off a Shopify
republish per drag.

`POST /api/tuning/preview` ranks one product under an unsaved tuning, in memory,
off the feature table on disk. It needs no token because it writes nothing.

---

## 11. Worked example

The web team wants Trending on the homepage.

1. They open the console, find the **Home Page** card, tick **Trending**, set
   the heading to "Trending Now" and slots to 8, and save.
2. The console validates the document, copies the current config to
   `ymal.config_previous`, and writes the new one with `metafieldsSet`.
3. The next homepage render reads the new config and shows the block.

No deploy. No theme edit. No engineer. That is the deliverable.

---

## 12. Open

- Do per-block options (§10) ever move into the console, and if so which?
- ~~Does `slots` belong here, or in the theme's own section settings?~~
  **Settled 2026-09-08: the theme editor wins.** The web team already places
  Wiser blocks that way and asked for the same workflow, so YMAL ships as a
  theme section (`sections/ymal-widget.liquid`) with block, heading, slots and
  page type as section settings. Wiser's appear under Apps because it is an
  installed app shipping theme app extensions; ours appear under Sections,
  which is the same drag with no app to host.

  **Consequence: the console's Setup Widgets screen is redundant** and section
  3's `placements` document is no longer the source of truth for placement.
  The metafields in section 2 are unaffected - the theme still reads the same
  published lists. Retire or repurpose Setup Widgets before the web team is
  told to use it, or they will have two places to set the same thing and no
  way to know which one won.
- One config for the whole store, or per market / per language? Wiser's screen
  has a language selector; nobody has said whether this store needs one.
- Should the pipeline read the config too — for instance, to skip computing a
  block nobody has enabled anywhere?
- Where does the holdout flag live — config, or engineering-owned settings? It
  affects revenue, so it probably should not be a checkbox.
