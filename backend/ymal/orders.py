"""
Windowed order-line extract — the input to Trending and Top Selling.

Only three things are needed from an order: which product, how many, and when.
Everything else (customer, address, payment) is deliberately not requested.

One function, one window argument. Trending and Top Selling are the same
extract with different dates — do not write it twice.

Note on the 60-day cap: without `read_all_orders`, Shopify serves only the last
60 days and does so SILENTLY — a 90-day window returns 60 days of data and looks
perfectly plausible. Measured 2026-09-04, this shop's credentials are NOT capped
(line items come back from 400 days ago), but `window_is_reachable()` stays
because credentials change and the failure leaves no trace.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from ymal import settings
from ymal.shopify import graphql, paginate

ORDERS_QUERY = """
query Orders($cursor: String, $filter: String!) {
  orders(first: %d, after: $cursor, query: $filter) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        createdAt
        lineItems(first: %d) {
          nodes {
            quantity
            product { id }
          }
        }
      }
    }
  }
}
""" % (settings.ORDERS_PAGE_SIZE, settings.ORDER_LINE_ITEMS_PAGE_SIZE)

ORDERS_COUNT_QUERY = """
query OrdersCount($filter: String!) {
  ordersCount(query: $filter, limit: 10000) { count precision }
}
"""


def day_bounds(days_ago_start: int, days_ago_end: int) -> tuple[str, str]:
    """
    An ISO date range, `days_ago_start` back to `days_ago_end` (exclusive end).

    day_bounds(14, 0)  -> the last 14 days
    day_bounds(28, 14) -> the 14 days before those
    """
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days_ago_start)).date().isoformat()
    end = (now - timedelta(days=days_ago_end)).date().isoformat()
    return start, end


def window_is_reachable(days_ago_start: int) -> bool:
    """
    False if the window reaches past what Shopify will serve.

    Callers should refuse rather than publish a ranking built on truncated
    history — the truncation is silent, which is what makes it dangerous.

    On this shop the cap does not apply (settings.ORDER_HISTORY_CAP_DAYS is
    None, measured 2026-09-04), so this returns True for any window. The check
    stays because credentials change and the failure mode is invisible.
    """
    cap = settings.ORDER_HISTORY_CAP_DAYS
    return cap is None or days_ago_start <= cap


def units_sold(days_ago_start: int, days_ago_end: int = 0) -> tuple[Counter, dict]:
    """
    Units sold per product GID within a window.

    Returns (counter, report). `report` carries the numbers worth printing:
    the window, how many orders and line items were seen, and how many orders
    hit the line-item page size — a sign their line items were truncated and
    the count for those products is low.
    """
    start, end = day_bounds(days_ago_start, days_ago_end)
    query_filter = f"created_at:>={start} AND created_at:<{end}"

    units: Counter = Counter()
    orders_seen = 0
    lines_seen = 0
    truncated: list[str] = []

    for order in paginate(ORDERS_QUERY, ["orders"], {"filter": query_filter}):
        orders_seen += 1
        lines = order["lineItems"]["nodes"]
        if len(lines) >= settings.ORDER_LINE_ITEMS_PAGE_SIZE:
            truncated.append(order["id"])

        for line in lines:
            lines_seen += 1
            product = line.get("product")
            # Deleted products come back null; there is nothing to rank.
            if not product or not product.get("id"):
                continue
            units[product["id"]] += line.get("quantity") or 0

    return units, {
        "window": f"{start} to {end}",
        "days": days_ago_start - days_ago_end,
        "orders": orders_seen,
        "line_items": lines_seen,
        "products_with_sales": len(units),
        "orders_with_truncated_lines": len(truncated),
    }


def count_orders(days_ago_start: int, days_ago_end: int = 0) -> dict:
    """Cheap pre-flight: how many orders the window holds, without pulling them."""
    start, end = day_bounds(days_ago_start, days_ago_end)
    data = graphql(
        ORDERS_COUNT_QUERY,
        {"filter": f"created_at:>={start} AND created_at:<{end}"},
    )
    return data["ordersCount"]
