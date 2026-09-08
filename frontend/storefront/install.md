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
| Product is `*SALE*` or fixed stock | Same - the gate rejects it, the script skips it. |
| `ymal.eligible` never published | Nothing renders. Fail closed, by design. Run the publish job. |
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

## The eligibility gate

**Settled 2026-09-05: the rule applies here too.** No `*SALE*` products, and
only unfix (Bali To Produce) products, exactly as everywhere else.

`templates/product.ymal-card.liquid` is the gate, and the only one. A product
renders only if all three hold:

| Check | Source |
|---|---|
| `product.available` | Liquid, live |
| title has no `*SALE*` | Liquid, live |
| `product.metafields.ymal.eligible` | published by `scripts/publish_eligibility.py` |

The third cannot be computed in Liquid - it sees store-wide inventory totals
but never inventory by location, so it has no way to know a product is stocked
at Bali To Produce.

**It fails closed.** A product with no `ymal.eligible` metafield does not
render. "We have not checked" must not display as "fine to show" - that is the
Wiser failure this project exists to fix. So run the publish job before
installing this, or the block will be empty:

```bash
cd backend
python -m scripts.publish_eligibility --dry-run
python -m scripts.publish_eligibility
```

Re-run it whenever eligibility changes - nightly, after `fetch_products`.
