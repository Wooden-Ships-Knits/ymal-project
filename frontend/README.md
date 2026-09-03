# YMAL — Frontend (JavaScript)

Storefront widget that renders the recommendations, plus the tracking that
measures it.

## Status

**Not started.** Frontend work begins at **Phase 6** (`docs/strategy.md`).
This folder is scaffolding — placed now so the monorepo structure is settled,
not because there is code to write yet.

Phases 1–5 are backend-only: eligible product list → feature table →
recommendations → publish to metafields. There is nothing for the frontend to
render until Phase 5 completes.

## Planned scope (Phase 6)

| Piece | Job |
|---|---|
| Theme snippet / app extension | Container + heading, placed via the theme editor |
| Card rendering | Reuse the **theme's existing** product card markup — must look native |
| Serve-time filtering | Re-check availability and the `*SALE*` marker at render |
| Tracking | `IntersectionObserver` impressions, delegated click handler, ATC |
| Fallback | Render from the metafield pool if the serving layer is unavailable |

## Design constraints (from `docs/frontend.md`)

- No layout shift — fixed aspect-ratio image containers.
- Empty state renders **nothing**, never a heading with no products.
- Real `<a>` links, alt text, keyboard-navigable.
- Mobile-first: carousel on mobile, grid on desktop.
- Theme must be backed up and previewed before any publish.
- A kill switch that restores Wiser without a deploy.

## Open

The serving model is not yet confirmed — metafield + Liquid (no JS fetch) vs
App Proxy backend (JS fetch). That decision shapes most of this folder.
See `docs/strategy.md` §6.
