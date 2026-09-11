"""
Build every block that can be computed from the backend, and report on each.

    trending      rising  — this 14-day window vs the previous one
    top_selling   volume  — units sold over 90 days
    new_arrivals  date    — published in the last 30 days

Featured and Recently Viewed are not here: Featured is per-product rather than
one store-wide list, and Recently Viewed has no backend at all.

Nothing here writes to Shopify. Output is JSON on disk — publishing is a
separate step, deliberately, so a bad run can be read before it reaches a
storefront.

Run:  cd backend && python -m scripts.build_blocks
      cd backend && python -m scripts.build_blocks trending

Output -> backend/data/blocks/<block>.json
"""

import json
import sys

from ymal import settings
from ymal.blocks import new_arrivals, top_selling, trending
from ymal.orders import count_orders, units_sold, window_is_reachable


def load_products() -> list[dict]:
    path = settings.PHASE1_DIR / "active_products.json"
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Run `python -m scripts.fetch_products` first — "
            "every block is filtered to eligible products, and that file is the list."
        )
    return json.loads(path.read_text())


def write(block: str, payload: dict) -> None:
    out_dir = settings.DATA_DIR / "blocks"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{block}.json").write_text(json.dumps(payload, indent=2))


def show(block: str, rows: list[dict], columns: list[tuple[str, str, int]]) -> None:
    """Print the top of a block's list. `columns` is (key, header, width)."""
    print(f"\n{'=' * 74}")
    print(f"{block.upper()}  —  {len(rows)} stored")
    print("=" * 74)
    header = "  " + " ".join(f"{h:>{w}}" for _, h, w in columns) + "  title"
    print(header)
    print("  " + "-" * (len(header) + 20))
    for row in rows[:12]:
        cells = " ".join(f"{row.get(k, ''):>{w}}" for k, _, w in columns)
        print(f"  {cells}  {row['title'][:42]}")
    if not rows:
        print("  (empty)")


def build_trending(products, eligible, titles, dedupe_by) -> None:
    days = settings.TRENDING_WINDOW_DAYS
    older = days * 2
    if not window_is_reachable(older):
        raise SystemExit(
            f"The comparison window reaches {older} days back, past what these "
            "credentials can read. Shopify truncates silently, so the ranking "
            "would be wrong but plausible. Shorten TRENDING_WINDOW_DAYS."
        )

    now, now_rep = units_sold(days, 0)
    before, before_rep = units_sold(older, days)
    print(f"  current  {now_rep['window']}: {now_rep['orders']} orders, "
          f"{now_rep['products_with_sales']} products sold")
    print(f"  previous {before_rep['window']}: {before_rep['orders']} orders, "
          f"{before_rep['products_with_sales']} products sold")

    rows = trending.rank(now, before, eligible=eligible, dedupe_by=dedupe_by)
    for row in rows:
        row["title"] = titles.get(row["product_gid"], "")

    write("trending", {
        "block": "trending",
        "definition": "rising: smoothed growth of this window over the previous one",
        "window_days": days,
        "current_window": now_rep["window"],
        "previous_window": before_rep["window"],
        "min_units": settings.TRENDING_MIN_UNITS,
        "smoothing": settings.TRENDING_SMOOTHING,
        "eligible_pool": len(eligible),
        "deduped_by": "title (colorway)",
        "items": rows,
    })
    show("trending", rows, [("score", "score", 6), ("units_now", "now", 5),
                            ("units_before", "before", 6)])


def build_top_selling(products, eligible, titles, dedupe_by) -> None:
    days = settings.TOP_SELLING_WINDOW_DAYS
    if not window_is_reachable(days):
        raise SystemExit(
            f"A {days}-day window is past what these credentials can read, and "
            "Shopify truncates silently. Shorten TOP_SELLING_WINDOW_DAYS or get "
            "read_all_orders approved."
        )

    print(f"  {count_orders(days, 0)['count']} orders in the last {days} days")
    units, report = units_sold(days, 0)
    print(f"  {report['window']}: {report['orders']} orders, "
          f"{report['products_with_sales']} products sold")

    rows = top_selling.rank(units, eligible=eligible, dedupe_by=dedupe_by)
    for row in rows:
        row["title"] = titles.get(row["product_gid"], "")

    write("top_selling", {
        "block": "top_selling",
        "definition": "plain volume: units sold over the window",
        "window_days": days,
        "window": report["window"],
        "eligible_pool": len(eligible),
        "deduped_by": "title (colorway)",
        "items": rows,
    })
    show("top_selling", rows, [("units", "units", 6)])

    # Every product's units, not just the ranked thirty. build_pools uses this
    # to nudge similar products by how well they sell, and counting them again
    # there would mean a second pull of the same orders.
    write("units", {
        "block": "units",
        "definition": "units sold per product over the Top Selling window",
        "window_days": days,
        "window": report["window"],
        "units": dict(units),
    })


def build_new_arrivals(products, eligible, titles, dedupe_by) -> None:
    days = settings.NEW_ARRIVALS_WINDOW_DAYS
    rows = new_arrivals.rank(products, window_days=days)
    print(f"  {len(rows)} eligible styles published in the last {days} days")

    write("new_arrivals", {
        "block": "new_arrivals",
        "definition": f"published within the last {days} days, newest first",
        "window_days": days,
        "eligible_pool": len(eligible),
        "deduped_by": "title (colorway)",
        "items": rows,
    })
    show("new_arrivals", [{**r, "published": r["published_at"][:10]} for r in rows],
         [("published", "published", 10)])


BUILDERS = {
    "trending": build_trending,
    "top_selling": build_top_selling,
    "new_arrivals": build_new_arrivals,
}


def main() -> None:
    wanted = sys.argv[1:] or list(BUILDERS)
    unknown = [w for w in wanted if w not in BUILDERS]
    if unknown:
        raise SystemExit(f"Unknown block(s): {unknown}. Choose from {list(BUILDERS)}.")

    products = load_products()
    eligible = {p["product_gid"] for p in products if p["eligible"]}
    titles = {p["product_gid"]: p["title"] for p in products}
    # Title doubles as the style key on this catalog: colorways of one style
    # share a title and differ by variant.
    dedupe_by = {gid: title.strip().upper() for gid, title in titles.items()}
    print(f"{len(eligible)} eligible products in the pool\n")

    for block in wanted:
        print(f"--- {block}")
        BUILDERS[block](products, eligible, titles, dedupe_by)

    print(f"\n  → {settings.DATA_DIR / 'blocks'}")
    print("  Nothing was written to Shopify. Publishing is a separate step.")


if __name__ == "__main__":
    main()
