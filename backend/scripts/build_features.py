"""
Phase 2 — build the product feature table.

One row per ELIGIBLE product, with everything content similarity needs. Reads
the Phase 1 list, fetches price and collections from Shopify, derives the rest.

Nothing here scores anything. It produces the inputs Phase 3 consumes.

Run:  cd backend && python -m scripts.build_features
Output -> backend/data/phase2/features.json and .csv
"""

import csv
import json

from ymal import features, settings
from ymal.catalog import fetch_product_features

OUT_DIR = settings.DATA_DIR / "phase2"

CSV_COLUMNS = [
    "product_id",
    "handle",
    "title",
    "style_key",
    "product_type_normalised",
    "price",
    "price_band",
    "season",
    "published_at",
    "signal_tag_count",
]


def load_eligible() -> list[dict]:
    path = settings.PHASE1_DIR / "active_products.json"
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Run `python -m scripts.fetch_products` first."
        )
    return [p for p in json.loads(path.read_text()) if p["eligible"]]


def write_outputs(rows: list[dict], report: dict) -> tuple:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUT_DIR / "features.json"
    json_path.write_text(json.dumps(rows, indent=2))

    csv_path = OUT_DIR / "features.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{k: row.get(k) for k in CSV_COLUMNS if k != "signal_tag_count"},
                    "signal_tag_count": len(row["signal_tags"]),
                }
            )

    report_path = OUT_DIR / "coverage.json"
    report_path.write_text(json.dumps(report, indent=2))
    return csv_path, json_path, report_path


def main() -> None:
    products = load_eligible()
    print(f"Eligible products: {len(products)}")

    print("Fetching price and collections...")
    extra = fetch_product_features()
    print(f"  {len(extra)} product(s) returned")

    rows = features.build_rows(products, extra)
    frequency = features.tag_document_frequency(products)
    report = features.coverage(rows, frequency, len(products))

    csv_path, json_path, report_path = write_outputs(rows, report)

    print("\n" + "=" * 52)
    print("PHASE 2 — PRODUCT FEATURE TABLE")
    print("=" * 52)
    print(f"  rows            : {report['products']}")
    print(f"  distinct styles : {report['styles']}")
    print()
    print("  tag coverage:")
    print(f"    distinct tags          {report['distinct_tags']}")
    print(f"    usable as signal       {report['signal_tags']}")
    print(f"    near-universal (drop)  {len(report['near_universal'])}")
    print(f"    on one product only    {report['single_product_tags']}")
    print(f"    per product: avg {report['signal_tags_per_product_avg']}, "
          f"min {report['signal_tags_per_product_min']}")
    print()
    print("  gaps:")
    print(f"    no signal tags         {report['products_with_no_signal_tags']}")
    print(f"    no season              {report['products_with_no_season']}")
    print(f"    no collections         {report['products_with_no_collections']}")

    print(f"\n  -> {csv_path}")
    print(f"  -> {json_path}")
    print(f"  -> {report_path}")

    problems = features.check(rows)
    print("\n" + "-" * 52)
    if problems:
        print("  FAILED SELF-CHECK - do not build recommendations on this:")
        for problem in problems:
            print(f"    {problem}")
    else:
        print("  OK: self-check passed. Every row has a style, a type, a")
        print("      price band and a unique id.")
    print("-" * 52)


if __name__ == "__main__":
    main()
