# Installing Recently Viewed

Ships on its own. No backend, no metafields, no config — the one block that can
go live before anything else exists.

**Back up the theme first.** Duplicate it, work on the copy, preview, publish.
Non-negotiable on a live store.

---

## 1. Copy three files into the theme

| From here | Into the theme |
|---|---|
| `assets/ymal-recently-viewed.js` | `assets/` |
| `snippets/ymal-recently-viewed.liquid` | `snippets/` |
| `templates/product.ymal-card.liquid` | `templates/` |

## 2. Point the card template at the theme's real card

`templates/product.ymal-card.liquid` ships with placeholder markup. Find the
theme's own card snippet — usually `snippets/card-product.liquid` or
`snippets/product-card.liquid` — and render that instead:

```liquid
{%- if product.available -%}
  {%- render 'card-product', card_product: product -%}
{%- endif -%}
```

This is the step that makes the block look native rather than bolted on. Do not
skip it and ship the placeholder.

## 3. Add the render tags

**`templates/product.liquid`** (or the product section), where the widget
should appear:

```liquid
{%- render 'ymal-recently-viewed',
      page_type: 'product',
      anchor: product,
      heading: 'Recently Viewed',
      slots: 4 -%}
```

`anchor: product` does two jobs — it records the product being viewed, and
keeps that product out of its own block.

**Anywhere else** (home, cart, collection), omit the anchor:

```liquid
{%- render 'ymal-recently-viewed', page_type: 'home', slots: 6 -%}
```

## 4. Check it

1. Open a product page. Nothing should appear — one view, and it is the anchor.
2. Open a second product. The first one appears.
3. Open a third. Two appear, newest first.
4. `localStorage.getItem('ymal:viewed')` in the console shows handles and
   timestamps, nothing else.
5. Sell out a test product, or unpublish it, and confirm it drops out of the
   block on the next load.
6. Open a private window. The block should be absent — not empty, absent.

---

## How it behaves

| Situation | What happens |
|---|---|
| No history yet | Section stays `hidden`. No empty heading. |
| Private browsing / storage blocked | Same — the storage call throws, is caught, and the block never unhides. |
| Product sold out since it was viewed | The card template renders nothing, the script skips it. |
| Product deleted or handle renamed | The fetch fails, the script skips it. |
| Fewer surviving cards than `slots` | Renders what it has. |
| Nothing survives | Section stays hidden. |

## What it stores

`{handle, id, ts}` — twenty entries, newest first. Nothing else, and it never
leaves the device. Title, price, image and availability are fetched fresh from
the theme on every render, so a handle stored three weeks ago still shows
today's price.

Per browser by nature: the same person on a phone and a laptop has two
different lists. Every store works this way; Wiser almost certainly included.

## Tracking

The script calls `window.ymalTrack(name, detail)` if it exists and does nothing
if it does not — so this block can ship before the events module does, and
starts reporting the moment that lands.

Events carry `block: 'recently_viewed'` and the page template. Without those
two fields the Analytics tab has nothing to group by.

## Open question this block raises

Should the eligibility gate apply here? The shopper chose to look at these
products. Hiding a `*SALE*` item someone just viewed is strange, so the current
behaviour filters on `product.available` only — purchasable, nothing more. If
that turns out to be wrong, the check lives in
`templates/product.ymal-card.liquid` and nowhere else.
