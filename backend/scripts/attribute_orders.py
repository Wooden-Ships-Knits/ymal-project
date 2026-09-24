"""
Phase 6 - attribute orders to the YMAL block that led to them.

When a shopper clicks a product in a YMAL row, the storefront writes a cart
attribute naming the block. Shopify carries cart attributes through checkout
onto the order, so a purchase can be attributed by reading them back - no
webhook, no session-to-order join, and nothing on the thank-you page, which
Shopify restricts.

TWO NUMBERS, deliberately. Attribution is LAST TOUCH: the attribute holds
whichever block the shopper clicked most recently before checking out.

  total         the whole order, including tax and shipping. Answers "orders
                that involved YMAL" - a shopper can click a recommendation,
                buy something else entirely, and still be counted. Generous,
                and the convention upsell apps report.

  direct_total  only the lines holding the product the shopper was actually
                recommended, and zero when they bought something else.
                Answers the stricter "YMAL sold this".

Neither is a claim that the block CAUSED the sale; the honest number for that
is the Phase 7 holdout.

Run:  cd backend && python -m scripts.attribute_orders
      cd backend && python -m scripts.attribute_orders --days 7
"""

import sys

from ymal import db, settings
from ymal.orders import day_bounds
from ymal.shopify import paginate

ATTRIBUTE_NAME = "YMAL block"
# Written beside it by the storefront: the handle of the product the shopper
# clicked or added. Orders placed before this existed simply have no direct
# figure, which reads as 0.
PRODUCT_ATTRIBUTE = "YMAL product"

ATTRIBUTED_ORDERS_QUERY = """
query AttributedOrders($cursor: String, $filter: String!) {
  orders(first: 100, after: $cursor, query: $filter) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        createdAt
        customAttributes { key value }
        currentTotalPriceSet { shopMoney { amount currencyCode } }
        lineItems(first: 100) {
          nodes {
            product { handle }
            customAttributes { key value }
            discountedTotalSet { shopMoney { amount } }
          }
        }
      }
    }
  }
}
"""


def _attribute(attributes: list | None, key: str) -> str | None:
    for attribute in attributes or []:
        if attribute.get("key") == key:
            value = (attribute.get("value") or "").strip()
            if value:
                return value
    return None


def block_of(order: dict) -> str | None:
    """The YMAL block named on the order, if any."""
    return _attribute(order.get("customAttributes"), ATTRIBUTE_NAME)


def product_of(order: dict) -> str | None:
    """The handle of the product the shopper was recommended, if any."""
    return _attribute(order.get("customAttributes"), PRODUCT_ATTRIBUTE)


def direct_total(order: dict, handle: str | None) -> float:
    """
    What the recommended product itself sold for in this order.

    Two ways a line counts, because the blocks reach the cart differently:

      - its product is the one named on the cart, which covers every block a
        shopper CLICKS through to the product page and buys from there;
      - the line carries a "YMAL block" attribute of its own, which the
        checkout block writes when it adds straight to the order.

    Discounted totals, so a half-price sweater counts what was actually paid.
    """
    total = 0.0
    for line in (order.get("lineItems") or {}).get("nodes") or []:
        product_handle = (line.get("product") or {}).get("handle")
        from_this_line = _attribute(line.get("customAttributes"), ATTRIBUTE_NAME)
        if (handle and product_handle == handle) or from_this_line:
            money = (line.get("discountedTotalSet") or {}).get("shopMoney") or {}
            total += float(money.get("amount") or 0)
    return round(total, 2)


def fetch(days: int) -> list[dict]:
    start, end = day_bounds(days, 0)
    query_filter = f"created_at:>={start} AND created_at:<{end}"

    rows = []
    for order in paginate(
        ATTRIBUTED_ORDERS_QUERY, ["orders"], {"filter": query_filter}
    ):
        block = block_of(order)
        if not block:
            continue
        money = (order.get("currentTotalPriceSet") or {}).get("shopMoney") or {}
        handle = product_of(order)
        rows.append(
            {
                "order_id": order["id"],
                "created_at": order["createdAt"],
                "block": block,
                "total": float(money.get("amount") or 0),
                "direct_total": direct_total(order, handle),
                "direct_product": handle,
                "currency": money.get("currencyCode") or "",
            }
        )
    return rows


def store(rows: list[dict]) -> int:
    """
    Upsert, so re-running is safe.

    Orders are immutable once placed, but the window overlaps between runs and
    a second insert of the same order would double the revenue it contributes.
    """
    if not rows:
        return 0

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO attributed_orders
                  (order_id, created_at, block, total, direct_total,
                   direct_product, currency)
                VALUES
                  (%(order_id)s, %(created_at)s, %(block)s, %(total)s,
                   %(direct_total)s, %(direct_product)s, %(currency)s)
                ON CONFLICT (order_id) DO UPDATE
                  SET block = EXCLUDED.block,
                      total = EXCLUDED.total,
                      direct_total = EXCLUDED.direct_total,
                      direct_product = EXCLUDED.direct_product,
                      currency = EXCLUDED.currency
                """,
                rows,
            )
    return len(rows)


def main() -> None:
    days = 30
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])

    print(f"Reading orders from the last {days} days...")
    rows = fetch(days)
    print(f"  {len(rows)} carried a '{ATTRIBUTE_NAME}' attribute")

    try:
        stored = store(rows)
    except db.NoDatabase as exc:
        raise SystemExit(f"Cannot store attributions: {exc}")

    by_block: dict[str, list[dict]] = {}
    for row in rows:
        by_block.setdefault(row["block"], []).append(row)

    print("\n" + "=" * 52)
    print("ATTRIBUTED ORDERS")
    print("=" * 52)
    print(f"  {'block':<18} {'orders':>6} {'whole order':>13} {'direct':>10}")
    for block, items in sorted(by_block.items(), key=lambda kv: -len(kv[1])):
        total = sum(i["total"] for i in items)
        direct = sum(i["direct_total"] for i in items)
        print(f"  {block:<18} {len(items):>6} {total:>13,.2f} {direct:>10,.2f}")
    if not by_block:
        print("  none yet - the storefront has not been tracking long enough,")
        print("  or the tracking script is not installed on the theme.")
    print(f"\n  stored {stored}")


if __name__ == "__main__":
    main()
