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

## 2. Two ways to render a block

**Preferred: the theme's own `product-list` section.** It already has the
slider, the aspect-ratio handling, quick buy and `product-block`, so a YMAL row
looks exactly like every other product row on the site and stays that way when
the theme changes.

Copy `sections/product-list.liquid` over the theme's copy. It adds one setting,
**Products from**, and leaves the collection behaviour as the default - so
every existing use of that section is unaffected.

Then in the theme editor: add a Product list section as usual, and set
**Products from** to a YMAL list instead of a collection.

**Alternative: the standalone `ymal-widget` section.** Self-contained, with its
own card and layout settings. Useful on a theme that has no reusable product
row, but on this store `product-list` is the better fit.

| File | Needed for |
|---|---|
| `sections/product-list.liquid` | the preferred route |
| `sections/ymal-widget.liquid` | the standalone route |
| `snippets/ymal-card.liquid` | the standalone route |
| `snippets/ymal-recently-viewed.liquid` | Recently Viewed, either route |
| `templates/product.ymal-card.liquid` | Recently Viewed, either route |
| `assets/ymal-recently-viewed.js` | Recently Viewed, either route |

Recently Viewed is not a `product-list` option: it has no metafield to read, so
it is rendered client-side from the shopper's browser and needs its own snippet.

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

The script calls `window.ymalTrack(name, detail)` if it exists and does nothing
if it does not, so blocks can ship before the events module does and start
reporting the moment it lands.

Events carry `block` and the page type. Without those two fields the Analytics
tab has nothing to group by.
