"""
Phase 6 - attribute orders to the YMAL block that led to them.

When a shopper clicks a product in a YMAL row, the storefront writes a cart
attribute naming the block. Shopify carries cart attributes through checkout
onto the order, so a purchase can be attributed by reading them back - no
webhook, no session-to-order join, and nothing on the thank-you page, which
Shopify restricts.

Attribution is LAST TOUCH: the attribute holds whichever block the shopper
clicked most recently before checking out. It is not a claim that the block
caused the sale; the honest number for that is the Phase 7 holdout.

Run:  cd backend && python -m scripts.attribute_orders
      cd backend && python -m scripts.attribute_orders --days 7
"""

import sys

from ymal import db, settings
from ymal.orders import day_bounds
from ymal.shopify import paginate

ATTRIBUTE_NAME = "YMAL block"

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
      }
    }
  }
}
"""


def block_of(order: dict) -> str | None:
    """The YMAL block named on the order, if any."""
    for attribute in order.get("customAttributes") or []:
        if attribute.get("key") == ATTRIBUTE_NAME:
            value = (attribute.get("value") or "").strip()
            if value:
                return value
    return None


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
        rows.append(
            {
                "order_id": order["id"],
                "created_at": order["createdAt"],
                "block": block,
                "total": float(money.get("amount") or 0),
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
                  (order_id, created_at, block, total, currency)
                VALUES
                  (%(order_id)s, %(created_at)s, %(block)s, %(total)s, %(currency)s)
                ON CONFLICT (order_id) DO UPDATE
                  SET block = EXCLUDED.block,
                      total = EXCLUDED.total,
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
    for block, items in sorted(by_block.items(), key=lambda kv: -len(kv[1])):
        total = sum(i["total"] for i in items)
        print(f"  {block:<18} {len(items):>4} orders   {total:>10,.2f}")
    if not by_block:
        print("  none yet - the storefront has not been tracking long enough,")
        print("  or the tracking script is not installed on the theme.")
    print(f"\n  stored {stored}")


if __name__ == "__main__":
    main()
