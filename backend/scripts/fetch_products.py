"""
Phase 1, step 2 — list active product pages and resolve eligibility.

Produces the Phase 1 deliverable: every ACTIVE product classified as eligible
("unfix") or not, with the reason it failed.

Rule (docs/logic.md §4.1) — both must hold:
    1. stocked at the Bali production location  -> replenishable
    2. title does NOT contain *SALE*            -> not markdown

Run:  cd backend && python -m scripts.fetch_locations   # confirm location name first
      cd backend && python -m scripts.fetch_products

Outputs → backend/data/phase1/
    active_products.csv     one row per active product
    active_products.json    same, as JSON
    summary.json            counts + the rule config that produced them
"""

import csv
import json
from collections import Counter

from ymal import settings
from ymal.catalog import (
    count_products,
    fetch_active_products,
    fetch_active_products_with_stock,
    fetch_stock_by_product,
    find_bali_locations,
    numeric_id,
)
from ymal.eligibility import classify

FIELDNAMES = [
    "product_id",
    "product_gid",
    "handle",
    "title",
    "product_type",
    "at_bali",
    "bali_available",
    "published",
    "total_inventory",
    "published_at",
    "tags",
    "eligible",
    "reason_if_not",
]


def build_rows(products: list[dict], bali_stock: dict[str, int]) -> list[dict]:
    rows = []
    for product in products:
        gid = product["id"]
        at_bali = gid in bali_stock
        eligible, reasons = classify(
            title=product["title"],
            at_bali=at_bali,
            bali_quantity=bali_stock.get(gid, 0),
            published=bool(product.get("onlineStoreUrl")),
        )
        rows.append({
            "product_id": numeric_id(gid),
            "product_gid": gid,
            "handle": product["handle"],
            "title": product["title"],
            "product_type": product.get("productType") or "",
            "at_bali": at_bali,
            "bali_available": bali_stock.get(gid, 0),
            "published": bool(product.get("onlineStoreUrl")),
            "total_inventory": product.get("totalInventory"),
            "published_at": product.get("publishedAt") or "",
            # Joined for the CSV; the JSON keeps the list (see write_outputs).
            "tags": ", ".join(product.get("tags") or []),
            "eligible": eligible,
            "reason_if_not": " + ".join(reasons),
        })
    return rows


def write_outputs(rows: list[dict], summary: dict) -> tuple:
    settings.PHASE1_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = settings.PHASE1_DIR / "active_products.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    json_path = settings.PHASE1_DIR / "active_products.json"
    json_path.write_text(json.dumps(rows, indent=2))

    (settings.PHASE1_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    return csv_path, json_path


def main() -> None:
    print("Resolving Bali location(s)...")
    bali_locations = find_bali_locations()

    if not bali_locations:
        raise SystemExit(
            f"No location matches BALI_LOCATION_PATTERN="
            f"{settings.BALI_LOCATION_PATTERN!r}.\n"
            "Run `python -m scripts.fetch_locations` to see the real names, "
            "then update ymal/settings.py. Without a match, every product "
            "would be misclassified as fixed stock."
        )

    print(f"  matched: {[loc['name'] for loc in bali_locations]}")

    if settings.SKIP_SALE_MARKED_IN_QUERY:
        skipped = count_products(f"status:active AND title:{settings.SALE_MARKER}")
        print(
            f"  SKIP_SALE_MARKED_IN_QUERY is on: {skipped} sale-marked active "
            "product(s) are excluded from the query below and won't appear "
            "in the CSV/JSON - only counted here."
        )

    if len(bali_locations) == 1:
        # Single location: join products to stock in one pass instead of
        # separately paging the location's whole inventory.
        print("Fetching active products with Bali inventory...")
        products, bali_stock, truncated_ids = fetch_active_products_with_stock(
            bali_locations[0]["id"]
        )
        print(f"  {len(products)} active product(s), {len(bali_stock)} of them stocked at Bali")
        if truncated_ids:
            print(
                f"  WARNING: {len(truncated_ids)} product(s) hit "
                f"VARIANTS_PAGE_SIZE ({settings.VARIANTS_PAGE_SIZE}) exactly - "
                "their variant count may be truncated, which can misclassify "
                "at_bali. Raise VARIANTS_PAGE_SIZE in settings.py. IDs: "
                f"{truncated_ids}"
            )
    else:
        # 0 or >1 matches: fall back to the general path, which can combine
        # stock across multiple locations.
        print("  WARNING: more than one match - confirm all are production locations")
        print("Fetching Bali inventory...")
        bali_stock = fetch_stock_by_product([loc["id"] for loc in bali_locations])
        print(f"  {len(bali_stock)} product(s) stocked at Bali")

        print("Fetching active products...")
        products = fetch_active_products()
        print(f"  {len(products)} active product(s)")

    if not products:
        raise SystemExit("No active products returned — check scopes and credentials.")

    rows = build_rows(products, bali_stock)
    eligible = [row for row in rows if row["eligible"]]

    reason_counter = Counter(
        row["reason_if_not"] for row in rows if not row["eligible"]
    )

    summary = {
        "active_products": len(rows),
        "eligible": len(eligible),
        "not_eligible": len(rows) - len(eligible),
        "eligible_pct": round(100 * len(eligible) / len(rows), 1),
        "exclusion_reasons": dict(reason_counter),
        "bali_locations": [loc["name"] for loc in bali_locations],
        "rule": {
            "bali_pattern": settings.BALI_LOCATION_PATTERN,
            "require_bali_quantity": settings.REQUIRE_BALI_QUANTITY,
            "sale_marker": settings.SALE_MARKER,
            "sale_marker_case_sensitive": settings.SALE_MARKER_CASE_SENSITIVE,
            "exclude_unpublished": settings.EXCLUDE_UNPUBLISHED,
        },
    }

    csv_path, json_path = write_outputs(rows, summary)

    print("\n" + "=" * 52)
    print("PHASE 1 — ELIGIBLE PRODUCT INVENTORY")
    print("=" * 52)
    print(f"  active products : {summary['active_products']}")
    print(f"  eligible        : {summary['eligible']} ({summary['eligible_pct']}%)")
    print(f"  not eligible    : {summary['not_eligible']}")
    if reason_counter:
        print("\n  excluded by:")
        for reason, count in reason_counter.most_common():
            print(f"    {reason:<32} {count}")
    print(f"\n  → {csv_path}")
    print(f"  → {json_path}")

    # The number Phase 1 exists to produce (docs/caveats.md §2).
    print("\n" + "-" * 52)
    if summary["eligible"] < 100:
        print("  WARNING: Under 100 eligible products. The 30-deep pool and")
        print("           6-slot widget both need revisiting - see caveats.md section 2.")
    elif summary["eligible"] < 500:
        print("  WARNING: Modest eligible catalog. Pool depth may need reducing;")
        print("           check that diversity rules stay satisfiable.")
    else:
        print("  OK: Eligible catalog looks large enough for a 30-deep pool.")
    print("-" * 52)


if __name__ == "__main__":
    main()
