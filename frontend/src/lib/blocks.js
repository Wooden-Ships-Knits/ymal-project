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
