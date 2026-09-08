"""
Phase 1 exit criterion 2: diff the API's eligible list against the Sheet.

The Sheet (caveats.md section 0) is the answer key - a hand-built list of
products believed eligible. This says where the two disagree and why.

Export the Sheet as CSV first: File > Download > Comma-separated values.

Run:  cd backend && python -m scripts.diff_sheet ~/Downloads/sheet.csv
      cd backend && python -m scripts.diff_sheet sheet.csv --id-column "Product ID"
"""

import csv
import json
import sys

from ymal import settings, sheet_diff

VERDICTS = {
    "match": (
        "MATCH: the rule agrees with the Sheet exactly.\n"
        "  Phase 1 criteria 2 and 3 are met. Record the count and close it."
    ),
    "api_larger": (
        "API LIST IS LARGER: the rule is too permissive.\n"
        "  Something ineligible is leaking through. See 'eligible per API, not\n"
        "  in the Sheet' below - each one is a product the widget would show\n"
        "  that you would not."
    ),
    "api_smaller": (
        "API LIST IS SMALLER: the rule is too strict.\n"
        "  Likely a location-name or marker-variant miss. The reason breakdown\n"
        "  below says which."
    ),
    "same_size_different_rows": (
        "SAME SIZE, DIFFERENT ROWS: the counts coincide but the products do\n"
        "  not. Read both lists below - this is two errors cancelling out."
    ),
}


def load_products() -> list[dict]:
    path = settings.PHASE1_DIR / "active_products.json"
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Run `python -m scripts.fetch_products` first."
        )
    return json.loads(path.read_text())


def load_sheet(path: str, id_column: str | None) -> tuple[list[dict], str]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise SystemExit(f"{path} has no rows.")

    headings = list(rows[0].keys())

    if id_column is None:
        id_column = sheet_diff.find_column(headings, sheet_diff.ID_HEADINGS)

    if id_column is None:
        raise SystemExit(
            "Could not find a product id column. Columns in the file:\n"
            + "\n".join(f"  {h}" for h in headings)
            + "\n\nRe-run with --id-column \"<the right one>\"."
        )

    if id_column not in headings:
        raise SystemExit(f"No column named {id_column!r}. Found: {headings}")

    return rows, id_column


def show(title: str, products: list[dict], limit: int = 40) -> None:
    if not products:
        return
    print()
    print(f"{title} ({len(products)})")
    print("-" * 72)
    for product in products[:limit]:
        reason = product.get("reason_if_not") or "-"
        print(f"  {product['product_id']:<16} {product['title'][:40]:<42} {reason}")
    if len(products) > limit:
        print(f"  ... and {len(products) - limit} more")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)

    id_column = None
    if "--id-column" in sys.argv:
        id_column = sys.argv[sys.argv.index("--id-column") + 1]

    products = load_products()
    rows, id_column = load_sheet(args[0], id_column)
    sheet_ids = sheet_diff.read_sheet_ids(rows, id_column)

    print(f"Sheet:  {args[0]}")
    print(f"        {len(rows)} rows, id column {id_column!r}, "
          f"{len(sheet_ids)} distinct product ids")
    print(f"API:    {len(products)} active products")
    print()

    result = sheet_diff.compare(products, sheet_ids)

    print(f"  Sheet says eligible    {result['sheet_count']}")
    print(f"  API says eligible      {result['api_eligible_count']}")
    print(f"  Both agree             {result['agreed']}")
    print()
    print(VERDICTS[result["verdict"]])

    grouped = sheet_diff.group_by_reason(result["missing_from_api"])
    if grouped:
        print()
        print("In the Sheet, but the API says ineligible - by reason:")
        for reason, items in grouped.items():
            print(f"  {reason:<28} {len(items)}")
        print()
        print("  One reason dominating means one broken assumption:")
        print("    fixed_stock  -> BALI_LOCATION_PATTERN is wrong, or a second")
        print("                    production location exists")
        print("    sale_marker  -> the marker is not exactly '*SALE*'")
        print("    not_published / no_product_type / excluded_type")
        print("                 -> a guard beyond the two stated conditions is")
        print("                    excluding products you consider eligible")

    show("In the Sheet, API says ineligible", result["missing_from_api"])
    show("Eligible per API, not in the Sheet", result["extra_in_api"])

    if result["not_in_catalog"]:
        print()
        print(f"In the Sheet, not in the active catalog at all "
              f"({len(result['not_in_catalog'])})")
        print("-" * 72)
        print("  Not a rule disagreement: gone inactive, deleted, or a bad id.")
        for pid in result["not_in_catalog"][:20]:
            print(f"  {pid}")

    print()
    if result["verdict"] == "match":
        print(f"OK: eligible product count is {result['api_eligible_count']}.")
    else:
        print("Next: explain each disagreement, or correct the rule in")
        print("ymal/settings.py and re-run fetch_products. Phase 1 closes when")
        print("every row is explained, not when the lists happen to match.")


if __name__ == "__main__":
    main()
