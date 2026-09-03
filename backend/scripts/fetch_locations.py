"""
Phase 1, step 1 — list every Shopify location.

Run this FIRST. The eligibility rule keys off the Bali production location, but
its exact name in Shopify is unconfirmed (docs/caveats.md §1). This prints the
real names so BALI_LOCATION_PATTERN can be set to something exact rather than
a guess.

Run:  cd backend && python -m scripts.fetch_locations
"""

import json

from ymal import settings
from ymal.catalog import fetch_locations, find_bali_locations


def main() -> None:
    locations = fetch_locations()

    print(f"\n{len(locations)} location(s):\n")
    print(f"{'name':<40} {'active':<8} {'country':<10} id")
    print("-" * 100)
    for loc in locations:
        address = loc.get("address") or {}
        print(
            f"{loc['name']:<40} "
            f"{str(loc['isActive']):<8} "
            f"{str(address.get('country') or '-'):<10} "
            f"{loc['id']}"
        )

    matches = find_bali_locations(locations)
    names = [m["name"] for m in matches]
    print(
        f"\nBALI_LOCATION_PATTERN = {settings.BALI_LOCATION_PATTERN!r} "
        f"matches {len(matches)}: {names or 'NONE'}"
    )

    if not matches:
        print(
            "\n⚠️  Nothing matched. Update BALI_LOCATION_PATTERN in "
            "ymal/settings.py before running fetch_products, or every product "
            "will be misclassified as fixed stock."
        )
    elif len(matches) > 1:
        print(
            "\n⚠️  Multiple matches. Confirm whether all of them count as "
            "production locations — see docs/caveats.md §1."
        )

    settings.PHASE1_DIR.mkdir(parents=True, exist_ok=True)
    out_path = settings.PHASE1_DIR / "locations.json"
    out_path.write_text(json.dumps(locations, indent=2))
    print(f"\nSaved → {out_path}")


if __name__ == "__main__":
    main()
