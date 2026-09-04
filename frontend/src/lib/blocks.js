/*
 * The five blocks. Mirrors the backend: adding one here without adding it in
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
    description: 'Plain volume over the last 90 days.',
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
]

export const blockById = (id) => BLOCKS.find((b) => b.id === id)
