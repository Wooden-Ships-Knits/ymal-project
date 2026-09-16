/*
 * YMAL — Recently Viewed, in checkout.
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
 * eligibility gate at view time - replenishable, not *SALE*.
 *
 * WHAT IS CHECKED HERE. Everything that can go stale between viewing and
 * checking out, and everything that depends on the cart:
 *   - the product still exists and is published
 *   - it is in stock right now, and so is the variant being offered
 *   - it is not already in this order
 *   - no other colorway of the same style is in this order either; a second
 *     Cocoon Wrap in another shade reads as a mistake, not a suggestion
 */
import '@shopify/ui-extensions/preact';
import { render } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';

export default function extension() {
  render(<Extension />, document.body);
}

const ATTRIBUTE = 'YMAL viewed';
const DEFAULT_SLOTS = 3;
// Ask for more than are shown: sold out, deleted and already-in-cart products
// all drop out below, and a row that thins to one card looks like a fault.
const LOOKUP_LIMIT = 12;

function productGid(id) {
  return 'gid://shopify/Product/' + String(id).trim();
}

function numericId(gid) {
  return String(gid).split('/').pop();
}

function sellableOf(product) {
  return ((product.variants && product.variants.nodes) || []).filter(
    (variant) => variant.availableForSale
  );
}

function styleOf(product) {
  // A style is its title, the same key the backend counts style sales under.
  // Colorways of one sweater are separate products sharing a title.
  return (product.title || '').trim().toUpperCase();
}

function Extension() {
  const { applyCartLinesChange, query, i18n, settings } = shopify;
  const attributes = shopify.attributes.value || [];
  const lines = shopify.lines.value || [];

  const [products, setProducts] = useState([]);
  const [adding, setAdding] = useState('');
  const [failed, setFailed] = useState(false);
  // The size dropdowns are uncontrolled: their value is read at Add time from
  // the element itself, so choosing a size never re-renders the row.
  const selects = useRef(new Map());

  const viewed = (attributes.find((a) => a.key === ATTRIBUTE) || {}).value || '';

  useEffect(() => {
    let current = true;
    const ids = viewed
      .split(',')
      .map((id) => id.trim())
      .filter(Boolean)
      .reverse()                 // oldest first
      .slice(0, LOOKUP_LIMIT)
      .map(productGid);

    if (!ids.length) {
      setProducts([]);
      return undefined;
    }

    query(
      `query ($ids: [ID!]!) {
        nodes(ids: $ids) {
          ... on Product {
            id
            title
            availableForSale
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
      }`,
      { variables: { ids } }
    )
      .then(({ data }) => {
        if (!current || !data) return;
        // `nodes` preserves the order asked for, so the oldest stays first.
        setProducts((data.nodes || []).filter(Boolean));
      })
      .catch(() => {
        // A recommendation is never worth breaking a checkout over.
        if (current) setProducts([]);
      });

    return () => {
      current = false;
    };
  }, [viewed]);

  const slots = Number(settings.current.products_to_show) || DEFAULT_SLOTS;
  const heading = settings.current.heading || 'Recently viewed';

  const inCartProducts = {};
  const inCartStyles = {};
  lines.forEach((line) => {
    const product = line.merchandise && line.merchandise.product;
    if (!product) return;
    inCartProducts[numericId(product.id)] = true;
    inCartStyles[(product.title || '').trim().toUpperCase()] = true;
  });

  const seenStyles = {};
  const offers = products
    .filter((product) => {
      if (!product.availableForSale) return false;
      if (inCartProducts[numericId(product.id)]) return false;

      const style = styleOf(product);
      if (inCartStyles[style] || seenStyles[style]) return false;
      if (!sellableOf(product).length) return false;

      // One colorway per style, keeping the oldest - the order is already the
      // order they were viewed in.
      seenStyles[style] = true;
      return true;
    })
    .slice(0, slots)
    .map((product) => ({ product, sellable: sellableOf(product) }));

  if (!offers.length) return null;

  async function add(productId, fallbackVariantId) {
    const select = selects.current.get(productId);
    const variantId = (select && select.value) || fallbackVariantId;

    setAdding(productId);
    setFailed(false);
    const result = await applyCartLinesChange({
      type: 'addCartLine',
      merchandiseId: variantId,
      quantity: 1,
      // The same marker every other YMAL placement writes, so a purchase made
      // from this block is attributed to it.
      attributes: [{ key: 'YMAL block', value: 'recently_viewed_checkout' }]
    });
    setAdding('');
    if (result.type === 'error') setFailed(true);
  }

  return (
    <s-stack direction="block" gap="base">
        {/* No s-section wrapper, and the heading is not passed as a section
            heading: each of those nests it one level deeper, and a heading's
            size comes from its nesting level. Nothing else about the size is
            ours to set - checkout extensions have no font-size control, so
            beyond this it follows the store's checkout typography settings. */}
        <s-stack direction="block" alignItems="center">
          <s-heading>{heading}</s-heading>
        </s-stack>

        {failed ? (
          <s-banner tone="critical">That product could not be added. Please try again.</s-banner>
        ) : null}

        {offers.map(({ product, sellable }) => {
          const variant = sellable[0];

          return (
            <s-box key={product.id} border="base" borderRadius="base" padding="base">
              {/* Image, details and the button share one row; the size picker
                  spans the full width beneath them, so a long product title
                  never pushes the button onto its own line. */}
              <s-grid gridTemplateColumns="auto 1fr auto" gap="base" alignItems="start">
                <s-product-thumbnail
                  src={product.featuredImage ? product.featuredImage.url : ''}
                  alt={product.title}
                  size="base"
                ></s-product-thumbnail>

                <s-stack direction="block" gap="small-500">
                  <s-text>{product.title}</s-text>
                  <s-text tone="neutral">
                    {i18n.formatCurrency(Number(variant.price.amount), {
                      currency: variant.price.currencyCode
                    })}
                  </s-text>
                </s-stack>

                <s-button
                  variant="primary"
                  onClick={() => add(product.id, variant.id)}
                  loading={adding === product.id}
                  disabled={Boolean(adding)}
                >
                  Add
                </s-button>

                {sellable.length > 1 ? (
                  <s-grid-item gridColumn="span 3">
                    <s-select
                      label="Size"
                      name={'ymal-variant-' + numericId(product.id)}
                      ref={(element) => {
                        selects.current.set(product.id, element);
                      }}
                    >
                      {sellable.map((v) => (
                        <s-option key={v.id} value={v.id}>
                          {v.title}
                        </s-option>
                      ))}
                    </s-select>
                  </s-grid-item>
                ) : null}
              </s-grid>
            </s-box>
          );
        })}
    </s-stack>
  );
}
