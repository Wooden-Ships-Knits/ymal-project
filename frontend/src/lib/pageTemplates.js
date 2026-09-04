/*
 * The page templates a block can be placed on.
 *
 * `v1` marks the two that ship first — Product and Home cover most of the
 * traffic and both are cheap. Wiser's nine is not a target; the list is
 * complete so that adding one later is configuration, not a schema change.
 */
export const PAGE_TEMPLATES = [
  { id: 'product',    label: 'Product Page',     v1: true,  anchor: true  },
  { id: 'home',       label: 'Home Page',        v1: true,  anchor: false },
  { id: 'cart',       label: 'Cart Page',        v1: false, anchor: false },
  { id: 'collection', label: 'Collection Pages', v1: false, anchor: false },
  { id: 'search',     label: 'Search Results',   v1: false, anchor: false },
  { id: 'not_found',  label: '404 Not Found',    v1: false, anchor: false },
  { id: 'blog',       label: 'Blog Posts',       v1: false, anchor: false },
  { id: 'account',    label: 'Account / Login',  v1: false, anchor: false },
  { id: 'thank_you',  label: 'Thank-you Page',   v1: false, anchor: false },
]

// A block needing an anchor product can only go where one exists.
export const blockAllowedOn = (block, template) =>
  !block.requiresAnchor || template.anchor
