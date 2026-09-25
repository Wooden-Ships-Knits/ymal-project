/*
 * YMAL — what Recently Viewed offers, shared by the checkout and Thank you
 * blocks.
 *
 * OLDEST FIRST, on purpose. Everywhere else Recently Viewed leads with the most
 * recent product. By checkout the recent ones are what the shopper just decided
 * against - the sweater they looked at an hour ago is the one worth showing
 * again.
 *
 * WHERE THE LIST COMES FROM. A checkout extension is sandboxed on another
 * origin: no localStorage, no Liquid, no metafields. The storefront writes the
 * shopper's viewed product ids onto the cart as the attribute "YMAL viewed"
 * (assets/ymal-recently-viewed.js), newest first, and only ids that passed the
 * eligibility gate at view time - replenishable, not *SALE*. Cart attributes
 * survive onto the order, which is why the Thank you page can read them too.
 */
export const ATTRIBUTE = 'YMAL viewed';
export const DEFAULT_SLOTS = 3;
// Ask for more than are shown: sold out, deleted and already-bought products
// all drop out below, and a row that thins to one card looks like a fault.
export const LOOKUP_LIMIT = 12;

export const PRODUCTS_QUERY = `query ($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on Product {
      id
      title
      availableForSale
      onlineStoreUrl
      featuredImage { url altText }
      variants(first: 20) {
        nodes {
          id
          title
          availableForSale
          price { amount currencyCode }
        }
      }
    }
  }
}`;

export function productGid(id) {
  return 'gid://shopify/Product/' + String(id).trim();
}

export function numericId(gid) {
  return String(gid).split('/').pop();
}

export function sellableOf(product) {
  return ((product.variants && product.variants.nodes) || []).filter(
    (variant) => variant.availableForSale
  );
}

export function styleOf(product) {
  // A style is its title, the same key the backend counts style sales under.
  // Colorways of one sweater are separate products sharing a title.
  return (product.title || '').trim().toUpperCase();
}

/* The ids to look up: oldest first, capped. */
export function lookupIds(attributes) {
  const viewed = (attributes || []).find((a) => a.key === ATTRIBUTE);
  return ((viewed && viewed.value) || '')
    .split(',')
    .map((id) => id.trim())
    .filter(Boolean)
    .reverse()
    .slice(0, LOOKUP_LIMIT)
    .map(productGid);
}

/*
 * What to show, given the products looked up and what the shopper has bought.
 *
 * Drops anything sold out, anything in the order, and any second colorway of a
 * style already in the order - offering another Cocoon Wrap in a different
 * shade reads as a mistake, not a suggestion.
 */
export function chooseOffers(products, lines, slots) {
  const boughtProducts = {};
  const boughtStyles = {};
  (lines || []).forEach((line) => {
    const product = line.merchandise && line.merchandise.product;
    if (!product) return;
    boughtProducts[numericId(product.id)] = true;
    boughtStyles[(product.title || '').trim().toUpperCase()] = true;
  });

  const seenStyles = {};
  return (products || [])
    .filter((product) => {
      if (!product || !product.availableForSale) return false;
      if (boughtProducts[numericId(product.id)]) return false;

      const style = styleOf(product);
      if (boughtStyles[style] || seenStyles[style]) return false;
      if (!sellableOf(product).length) return false;

      seenStyles[style] = true;
      return true;
    })
    .slice(0, slots)
    .map((product) => ({ product, sellable: sellableOf(product) }));
}
