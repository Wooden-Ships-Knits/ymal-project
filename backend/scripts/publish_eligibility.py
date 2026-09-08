"""
Publish the eligible flag to each product's ymal.eligible metafield.

The theme cannot compute eligibility - Liquid cannot see inventory by location -
so this is how the rule reaches the storefront. Every block's card template
checks this metafield and fails closed when it is missing.

Reads backend/data/phase1/active_products.json. Run fetch_products first; this
publishes that file, it does not recompute anything.

Run:  cd backend && python -m scripts.publish_eligibility --dry-run
      cd backend && python -m scripts.publish_eligibility
"""

import sys

from ymal import publish


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    products = publish.load_products()
    print(f"Loaded {len(products)} active products.")

    if dry_run:
        print("DRY RUN: nothing will be written.")

    result = publish.publish(products, dry_run=dry_run)

    print()
    print(f"  eligible      {result['eligible']}")
    print(f"  not eligible  {result['not_eligible']}")
    print(f"  batches       {result['batches']}")

    if result["dry_run"]:
        print()
        print("Nothing written. Re-run without --dry-run to publish.")
        return

    print(f"  written       {result['written']}")
    print()
    print("OK: product.metafields.ymal.eligible is now current.")


if __name__ == "__main__":
    main()
