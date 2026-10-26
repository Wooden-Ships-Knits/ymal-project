/*
 * The six blocks. Mirrors the backend: adding one here without adding it in
 * ymal/blocks/ produces a page that configures something nothing computes, so
 * the console warns rather than silently offering it.
 */
export const BLOCKS = [
  {
    id: 'featured',
    label: 'Featured Products',
    description: 'Products sharing tags with the one being viewed.',
    requiresAnchor: true,
    defaultHeading: 'You May Also Like',
    defaultSlots: 6,
  },
  {
    id: 'trending',
    label: 'Trending Products',
    description: 'Rising: selling more in the last 14 days than the 14 before.',
    requiresAnchor: false,
    defaultHeading: 'Trending Now',
    defaultSlots: 6,
  },
  {
    id: 'top_selling',
    label: 'Top Selling',
    // 14 days since 2026-09-10. This is the offline fallback copy; the
    // server's registry.py builds the same line from settings and wins
    // whenever the API is reachable.
    description: 'Plain volume over the last 14 days.',
    requiresAnchor: false,
    defaultHeading: 'Top Selling',
    defaultSlots: 6,
  },
  {
    id: 'new_arrivals',
    label: 'New Arrivals',
    description: 'Published in the last 30 days, newest first.',
    requiresAnchor: false,
    defaultHeading: 'New Arrivals',
    defaultSlots: 6,
  },
  {
    id: 'recently_viewed',
    label: 'Recently Viewed',
    description: "The shopper's own history. Lives in their browser, not on our server.",
    requiresAnchor: false,
    defaultHeading: 'Recently Viewed',
    defaultSlots: 4,
  },
  {
    id: 'inspired_by_views',
    label: 'Inspired By Your Views',
    description:
      "The top 4 Featured products of the shopper's last 5 viewed products, minus anything already viewed or in the cart, shuffled once per visit.",
    requiresAnchor: false,
    defaultHeading: 'Inspired By Your Views',
    defaultSlots: 4,
  },
  {
    id: 'cart_popup',
    label: 'Add to Cart Popup',
    description:
      'Shown the moment a product is added: the Featured list of the product just added, ordered by what shoppers actually buy in the same order.',
    requiresAnchor: false,
    defaultHeading: 'Pairs well with',
    defaultSlots: 3,
  },
]

export const blockById = (id) => BLOCKS.find((b) => b.id === id)

/*
 * What each block is CALLED on screen, which is not what it is called in the
 * data. The ids are written into events, orders and the theme's settings and
 * cannot be renamed without orphaning everything already recorded under them;
 * these are the web team's own names for the same things, including the names
 * the storefront team uses with the boss ("MYNTS").
 *
 * Display only. Nothing here reaches the API, the storefront or the database.
 */
export const BLOCK_LABELS = {
  featured: 'Featured (YMAL)',
  cart_popup: 'Cart Popup',
  recently_viewed: 'Recently Viewed',
  inspired_by_views: 'Inspired By Your Views (IBYV)',
  top_selling: 'Top Selling/More You Need To See (MYNTS)',
  trending: 'Trending',
  new_arrivals: 'New Arrivals',
}

/* A/B placements are the same block under two names: label the base, add the
   letter, so a test shows as "... (MYNTS) A" rather than as a stranger. */
export function blockLabel(id) {
  if (BLOCK_LABELS[id]) return BLOCK_LABELS[id]

  const match = /^(.*)_(a|b)$/.exec(id || '')
  if (match && BLOCK_LABELS[match[1]]) {
    return `${BLOCK_LABELS[match[1]]} ${match[2].toUpperCase()}`
  }

  // An id nobody has named yet still has to read as something.
  return String(id || '').replace(/_/g, ' ')
}
