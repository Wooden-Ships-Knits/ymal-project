"""
New Arrivals — published within the last N days, newest first.

The simplest block in the set: a date filter and a sort. No orders, no scoring,
no model. It reads the Phase 1 product list, which already carries publishedAt.

Pure functions, no I/O.
"""

from datetime import datetime, timedelta, timezone

from ymal import settings


def parse_published(value: str | None) -> datetime | None:
    """Shopify's ISO-8601 timestamp, or None if absent or unparseable."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def rank(
    products: list[dict],
    window_days: int | None = None,
    limit: int | None = None,
    dedupe_by_title: bool = True,
) -> list[dict]:
    """
    Eligible products published inside the window, newest first.

    `products` is the Phase 1 row shape — it must carry `eligible`,
    `published_at` and `title`.

    Colorway dedupe applies here as everywhere: a style is normally published in
    every colour on the same day, so without it the block is one sweater
    repeated.
    """
    days = settings.NEW_ARRIVALS_WINDOW_DAYS if window_days is None else window_days
    depth = settings.STORED_LIST_DEPTH if limit is None else limit
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = []
    for product in products:
        if not product.get("eligible"):
            continue
        published = parse_published(product.get("published_at"))
        if published is None or published < cutoff:
            continue
        rows.append({
            "product_gid": product["product_gid"],
            "product_id": product["product_id"],
            "title": product["title"],
            "published_at": product["published_at"],
            "_sort": published,
        })

    rows.sort(key=lambda r: r["_sort"], reverse=True)

    if dedupe_by_title:
        seen: set[str] = set()
        deduped = []
        for row in rows:
            key = row["title"].strip().upper()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        rows = deduped

    for row in rows:
        del row["_sort"]
    return rows[:depth]
