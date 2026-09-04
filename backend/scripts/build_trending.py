"""
Build the Trending block — products selling more than they were.

Two order windows of equal length, back to back: the last TRENDING_WINDOW_DAYS
against the ones before them. Rank by smoothed growth, filtered to eligible
products first.

Run:  cd backend && python -m scripts.build_trending

Output -> backend/data/blocks/trending.json
"""

import json

from ymal import settings
from ymal.blocks.trending import rank
from ymal.catalog import numeric_id
from ymal.orders import count_orders, units_sold, window_is_reachable


def load_eligible() -> tuple[set[str], dict[str, str]]:
    """Eligible product GIDs, and GID -> title (also the colorway dedupe key)."""
    path = settings.PHASE1_DIR / "active_products.json"
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Run `python -m scripts.fetch_products` first — "
            "Trending is filtered to eligible products, and that file is the list."
        )
    rows = json.loads(path.read_text())
    eligible = {r["product_gid"] for r in rows if r["eligible"]}
    titles = {r["product_gid"]: r["title"] for r in rows}
    return eligible, titles


def main() -> None:
    days = settings.TRENDING_WINDOW_DAYS
    older_start = days * 2

    if not window_is_reachable(older_start):
        raise SystemExit(
            f"The comparison window reaches {older_start} days back, past the "
            "60-day cap that applies without read_all_orders. Shopify would "
            "return truncated history without saying so, and the ranking would "
            "be wrong but plausible. Shorten TRENDING_WINDOW_DAYS or get the "
            "scope approved."
        )

    eligible, titles = load_eligible()
    print(f"{len(eligible)} eligible products to rank against\n")

    print("Counting orders...")
    print(f"  current  : {count_orders(days, 0)['count']} orders")
    print(f"  previous : {count_orders(older_start, days)['count']} orders")

    print("\nPulling current window...")
    now, now_report = units_sold(days, 0)
    print(f"  {now_report['window']}  {now_report['orders']} orders, "
          f"{now_report['line_items']} lines, {now_report['products_with_sales']} products sold")

    print("Pulling previous window...")
    before, before_report = units_sold(older_start, days)
    print(f"  {before_report['window']}  {before_report['orders']} orders, "
          f"{before_report['line_items']} lines, {before_report['products_with_sales']} products sold")

    for report in (now_report, before_report):
        if report["orders_with_truncated_lines"]:
            print(f"  WARNING: {report['orders_with_truncated_lines']} order(s) hit "
                  f"ORDER_LINE_ITEMS_PAGE_SIZE ({settings.ORDER_LINE_ITEMS_PAGE_SIZE}). "
                  "Their line items may be truncated and those products undercounted.")

    # Title doubles as the style key on this catalog: colorways of one style
    # share a title and differ by variant. PPA's style tag (tags[0]) is the
    # more principled key if titles ever diverge.
    dedupe_by = {gid: title.strip().upper() for gid, title in titles.items()}

    rows = rank(now, before, eligible=eligible, dedupe_by=dedupe_by)
    for row in rows:
        row["product_id"] = numeric_id(row["product_gid"])
        row["title"] = titles.get(row["product_gid"], "")

    out_dir = settings.DATA_DIR / "blocks"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "block": "trending",
        "definition": "rising: smoothed growth of this window over the previous one",
        "window_days": days,
        "current_window": now_report["window"],
        "previous_window": before_report["window"],
        "min_units": settings.TRENDING_MIN_UNITS,
        "smoothing": settings.TRENDING_SMOOTHING,
        "depth": settings.STORED_LIST_DEPTH,
        "eligible_pool": len(eligible),
        "deduped_by": "title (colorway)",
        "items": rows,
    }
    out_path = out_dir / "trending.json"
    out_path.write_text(json.dumps(payload, indent=2))

    print("\n" + "=" * 72)
    print(f"TRENDING — rising over {days} days, top {len(rows)} of {len(eligible)} eligible")
    print("=" * 72)
    print(f"  {'score':>6} {'now':>5} {'before':>7}  title")
    print("  " + "-" * 68)
    for row in rows[:15]:
        print(f"  {row['score']:>6.2f} {row['units_now']:>5} {row['units_before']:>7}  {row['title'][:44]}")

    if not rows:
        print("  Nothing cleared the bar. Lower TRENDING_MIN_UNITS "
              f"(currently {settings.TRENDING_MIN_UNITS}) or widen the window.")
    print(f"\n  → {out_path}")


if __name__ == "__main__":
    main()
