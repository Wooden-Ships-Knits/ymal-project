/*
 * YMAL — Recently Viewed, in checkout.
 *
 * The list and the rules live in ./offers.js, shared with the Thank you block.
 * What is specific here is that the order is not placed yet, so a product can
 * still be ADDED to it - the whole point of the block at this moment.
 *
 * Checked here because it can change between viewing and checking out: the
 * product still exists and is published, is in stock right now, is not already
 * in the order, and is not another colorway of a style already in it.
 */
import '@shopify/ui-extensions/preact';
import { render } from 'preact';
import { useEffect, useRef, useState } from 'preact/hooks';
import {
  chooseOffers,
  DEFAULT_SLOTS,
  lookupIds,
  numericId,
  PRODUCTS_QUERY
} from './offers.js';

export default function extension() {
  render(<Extension />, document.body);
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

  // The effect's dependency: re-run only when the list itself changes.
  const viewed = JSON.stringify(lookupIds(attributes));

  useEffect(() => {
    let current = true;
    const ids = lookupIds(attributes);

    if (!ids.length) {
      setProducts([]);
      return undefined;
    }

    query(PRODUCTS_QUERY, { variables: { ids } })
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

  const offers = chooseOffers(products, lines, slots);

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
