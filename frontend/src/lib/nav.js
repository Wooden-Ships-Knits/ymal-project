/*
 * The sidebar, mirroring the Wiser console it replaces.
 *
 * `status` is deliberate and shown in the UI:
 *   'planned'  — a screen this project will build
 *   'later'    — in scope eventually, nothing behind it yet
 *   'n/a'      — a Wiser feature this project does not replace. Kept in the
 *                nav only so the web team can see it is gone on purpose
 *                rather than wonder where it went.
 *
 * Nothing here is billing, search or app management: those were Wiser's
 * business, not ours.
 */
export const NAV = [
  { id: 'dashboard',       label: 'Dashboard',              status: 'later'   },
  { id: 'setup',           label: 'Setup Widgets',          status: 'planned' },
  { id: 'recommendations', label: 'Recommendations',        status: 'planned' },
  { id: 'customize',       label: 'Customize Widgets',      status: 'later'   },
  { id: 'search',          label: 'Intelli Search and Filter', status: 'n/a'  },
  { id: 'addons',          label: 'Product Addons',         status: 'n/a'     },
  { id: 'analytics',       label: 'Analytics',              status: 'planned' },
  { id: 'cart',            label: 'Cart Drawer',            status: 'n/a'     },
  { id: 'plan',            label: 'My Plan',                status: 'n/a'     },
  { id: 'exclude',         label: 'Exclude Products',       status: 'planned' },
]

// Wiser tucks the rarely-used items behind a "More" toggle. Same here.
export const NAV_MORE = [
  { id: 'translations', label: 'Translations', status: 'later'   },
  { id: 'cache',        label: 'Flush Cache',  status: 'planned' },
]

export const STATUS_LABEL = {
  planned: 'planned',
  later: 'later',
  'n/a': 'not replaced',
}
