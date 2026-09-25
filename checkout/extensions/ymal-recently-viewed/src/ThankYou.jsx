/*
 * YMAL — Recently Viewed, on the Thank you page.
 *
 * The same list and the same rules as the checkout block (./offers.js), read
 * from the same cart attribute, which survives onto the order.
 *
 * NO ADD BUTTON, and that is not an omission. Thank you page targets have read
 * access only - the order is complete, and Shopify allows no mutation from
 * here. So each card LINKS to the product instead. The ask is different too:
 * checkout asks "one more before you pay", this asks "worth a look next time",
 * which is why it sits below a line saying the order is on its way rather than
 * pretending to be an upsell.
 *
 * Nothing is tracked from here: the extension has no network access, so its
 * views and clicks do not reach the console. A shopper who follows a link
 * lands on the storefront, where the usual tracking takes over.
 */
import '@shopify/ui-extensions/preact';
import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { chooseOffers, DEFAULT_SLOTS, lookupIds, PRODUCTS_QUERY } from './offers.js';

export default function extension() {
  render(<Extension />, document.body);
}

function Extension() {
  const { query, i18n, settings } = shopify;
  const attributes = shopify.attributes.value || [];
  const lines = shopify.lines.value || [];

  const [products, setProducts] = useState([]);
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
        setProducts((data.nodes || []).filter(Boolean));
      })
      .catch(() => {
        // A suggestion is never worth breaking an order confirmation over.
        if (current) setProducts([]);
      });

    return () => {
      current = false;
    };
  }, [viewed]);

  const slots = Number(settings.current.products_to_show) || DEFAULT_SLOTS;
  const heading = settings.current.heading || 'Still thinking about these?';
  const offers = chooseOffers(products, lines, slots);

  if (!offers.length) return null;

  return (
    <s-stack direction="block" gap="base">
      <s-stack direction="block" alignItems="center">
        <s-heading>{heading}</s-heading>
      </s-stack>

      {offers.map(({ product, sellable }) => {
        const variant = sellable[0];

        return (
          <s-box key={product.id} border="base" borderRadius="base" padding="base">
            <s-grid gridTemplateColumns="auto 1fr auto" gap="base" alignItems="center">
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

              {/* A link, not a button: the order is placed and cannot be added
                  to from here. `onlineStoreUrl` is null for a product that is
                  not published to the online store, and there is nowhere to
                  send anyone then. */}
              {product.onlineStoreUrl ? (
                <s-button href={product.onlineStoreUrl} target="_blank" variant="secondary">
                  View
                </s-button>
              ) : null}
            </s-grid>
          </s-box>
        );
      })}
    </s-stack>
  );
}
