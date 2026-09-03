# YMAL — Frontend

How recommendations actually reach the shopper. Draft for discussion.

---

## 1. Integration approach

Three ways to get a widget onto a Shopify storefront:

| Approach | What it is | Verdict |
|---|---|---|
| **Theme app extension** | App block the team drags into the theme editor | Correct for a distributed app; overkill for one store |
| **Theme section/snippet** | Liquid file added to the theme, rendered server-side | ⭐ Simplest for a single store we own |
| **Script injection** | JS bundle that injects markup client-side | How Wiser works. Slower, flashes, worse SEO |

**Leaning: theme snippet**, rendered server-side from the metafield. Fastest
to ship, fastest to load, no layout shift, no dependency on our uptime.

If we go with backend Option B (live API), this becomes a JS fetch instead and
the tradeoffs flip.

---

## 2. Placements

| Placement | Anchor | Priority |
|---|---|---|
| **Product page** — below description | current product | v1 — replaces Wiser |
| **Cart / cart drawer** | cart contents | v2 — highest AOV impact |
| **Collection page** | collection | v3 |
| **Homepage** | customer history | v3, needs personalization |
| **Empty search results** | query | nice-to-have, rescues dead ends |
| **Post-purchase / thank-you** | order | v3 |

v1 scope should be product page only — direct like-for-like against Wiser so
the comparison is clean.

---

## 3. Rendering (Option A — server-side Liquid)

```liquid
{%- comment -%} snippets/ymal.liquid {%- endcomment -%}
{%- assign recs = product.metafields.ymal.recommendations.value -%}

{%- if recs != blank -%}
  <section class="ymal" data-anchor="{{ product.id }}">
    <h2 class="ymal__title">{{ section.settings.heading | default: 'You May Also Like' }}</h2>
    <ul class="ymal__grid">
      {%- for item in recs limit: 6 -%}
        {%- if item.available -%}
          <li class="ymal__card" data-product-id="{{ item.id }}" data-position="{{ forloop.index }}">
            <a href="{{ item.url }}">
              <img src="{{ item.featured_image | image_url: width: 400 }}"
                   alt="{{ item.featured_image.alt | escape }}"
                   loading="lazy" width="400" height="600">
              <span class="ymal__name">{{ item.title }}</span>
              <span class="ymal__price">{{ item.price | money }}</span>
            </a>
          </li>
        {%- endif -%}
      {%- endfor -%}
    </ul>
  </section>
{%- endif -%}
```

Note the `item.available` check — a second line of defence. The nightly job
filters out-of-stock items, but stock moves during the day and a metafield
written at 03:00 goes stale. Liquid re-checks at render time.

---

## 4. Design requirements

- **Reuse the theme's existing product card.** Do not invent new markup —
  it must look native, not bolted on. If the theme has a card snippet, call it.
- **Color swatches.** The store has swatch assets (cf. `thumbnails/swatch-color`
  in sibling projects). Decide whether YMAL cards show swatches — they help,
  but add weight.
- **Mobile-first.** Horizontal scroll carousel on mobile, grid on desktop, is
  the common pattern. Confirm against the current theme.
- **No layout shift.** Fixed aspect-ratio image containers.
- **Empty state = render nothing.** Never an empty heading with no products.
- **Accessibility.** Real `<a>` links, alt text, keyboard-navigable carousel,
  a heading in the document outline.

---

## 5. Tracking — required, not optional

Without this we cannot prove we beat Wiser.

| Event | When | Payload |
|---|---|---|
| `ymal_impression` | widget enters viewport | anchor id, rec ids, positions |
| `ymal_click` | card clicked | anchor id, clicked id, position |
| `ymal_add_to_cart` | ATC from a rec'd product | anchor id, product id |

Use an `IntersectionObserver` for impressions (fires once per pageview, not on
every scroll) and delegate clicks from the container.

**Open question: where does this land?** Options — Shopify Web Pixels, GA4,
or our own endpoint. Whatever the store already uses for analytics is the
right answer; no need for a new pipe.

---

## 6. Rollout & safety

- **Back up the theme before touching it.** Duplicate, work on the copy,
  preview, then publish. Non-negotiable on a live store.
- **A/B against Wiser** — split by a stable hash of session or customer id, so
  a shopper sees a consistent experience. Run both widgets in parallel; do not
  remove Wiser until the numbers are in.
- **Kill switch** — a theme setting that hides our widget and restores Wiser
  without a code deploy.
- Keep Wiser installed through the whole trial. Uninstalling early leaves no
  fallback if ours underperforms.

---

## 7. Open questions

- What theme is the store on, and does it use Online Store 2.0 sections?
- Where exactly does Wiser's widget currently sit on the product page?
- How many slots? (4 / 6 / 8 — affects the diversity rules in `logic.md`)
- Carousel or static grid?
- Which analytics destination for the tracking events?
- Who has theme edit rights, and what's the approval path for publishing?
