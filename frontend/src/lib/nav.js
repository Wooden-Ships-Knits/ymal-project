/*
 * The sidebar.
 *
 * Cut from twelve tabs to four on 2026-09-09. The original mirrored Wiser's
 * console so the web team would recognise it, but most of those screens either
 * duplicated something better or had nothing behind them:
 *
 *   Setup Widgets      superseded. Placement moved to the Shopify theme
 *                      editor, where the web team already works. Two places to
 *                      set the same thing is worse than one.
 *   Recommendations,   Wiser features this project does not replace, or
 *   Customize, Search, screens with no backend behind them. A tab that does
 *   Addons, Cart,      nothing teaches people the console does nothing.
 *   Plan, Translations
 *   Flush Cache        there is no cache to flush.
 *
 * What is left is what only this console can do.
 */
export const NAV = [
  { id: 'dashboard', label: 'Dashboard',        status: 'planned' },
  { id: 'analytics', label: 'Analytics',        status: 'planned' },
  { id: 'exclude',   label: 'Exclude Products', status: 'planned' },
  { id: 'run',       label: 'Manual Update',    status: 'live'    },
]

// Nothing is hidden behind a "More" toggle any more - four tabs all fit.
export const NAV_MORE = []

export const STATUS_LABEL = {
  live: '',
  planned: 'planned',
  later: 'later',
  'n/a': 'not replaced',
}
