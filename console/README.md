# YMAL — Console (admin)

The screen the web admin team uses to decide which recommendation blocks appear
on which page, and to see what each one earns.

Modelled on Wiser's "Active Widgets" screen — see `docs/ymal-flow.drawio` page 5.

## Status

**Not started.** This folder is scaffolding.

## Stack — decided 2026-09-04

| Layer | Choice |
|---|---|
| Frontend | JavaScript (React with a build, or plain JS — still open, not blocking) |
| Backend | FastAPI, importing the `ymal` package from `backend/` |
| Deploy | Docker on the existing VM, behind the host nginx, password-gated |

The deployment pattern is PPA's, which already runs this way
(`PPA/docker-compose.yml`, `PPA/deploy/ppa.nginx.conf`). What changes is the UI
layer: a real web page instead of Streamlit.

**Streamlit was rejected** — fastest to build, but it looks like a tool and the
look is part of the ask. **A Shopify embedded app was deferred**, not ruled out:
it would sit inside the Shopify admin and look native, but needs App Bridge,
session-token auth inside an iframe, an app registration and a Node stack the
team does not run. Because the console's only job is writing one metafield, it
can be swapped later without touching the pipeline or the theme.

## Security

**Shopify credentials never reach the browser.** The JS page calls our API; our
API talks to Shopify using the existing `ymal.auth` token exchange.

If reusing PPA's compose pattern, do not inherit its default password — its own
file flags that as needing changing — and keep the app on the VM's loopback
behind nginx, as PPA does.

## Screens

| Screen | Version | Job |
|---|---|---|
| Setup Widgets | v1 | A card per page template. Which blocks, in what order, how many slots, what heading. |
| Analytics | v1, after events exist | Per block and per page: impressions, clicks, CTR, attributed revenue. |
| Exclude Products | v2 | The merchandiser block list — where the Google Sheet was always heading. |
| Customize Widgets | later | Headings, card layout, carousel vs grid. |
| Dashboard | later | The summary view. Nothing to summarise yet. |

## API

The frontend talks only to these. See `docs/config-contract.md` for shapes.

```
GET  /api/config          current configuration
PUT  /api/config          validate, archive the previous version, write to Shopify
GET  /api/blocks          available blocks + which page templates each supports
GET  /api/page-templates  the fixed list of page templates
GET  /api/analytics       per-block metrics (once the event store exists)
```

## The rule that governs this whole folder

**The console writes `ymal.config` and nothing else.** It does not compute
recommendations, does not write product data, and is never in the path of a
storefront request. If the console is down, the storefront is unaffected.

A malformed config would silently blank every block, so `PUT /api/config`
validates before writing and keeps the previous version for one-click undo.
