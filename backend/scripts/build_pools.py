"""
Phase 3 — build a candidate pool for every eligible product.

Content similarity only: motif, fabric, colour, silhouette, with season as a
hard filter. No order history, so this works for a product launched today -
it is the permanent cold-start path, not just a stepping stone to Phase 4.

Reads the Phase 2 feature table. Writes JSON on disk; publishing to Shopify is
Phase 5 and deliberately separate, so a bad run can be read before it reaches
a storefront.

Run:  cd backend && python -m scripts.build_pools
      cd backend && python -m scripts.build_pools --show "CHARLOTTE CREW COTTON"
Output -> backend/data/phase3/pools.json
"""

import json
import statistics
import sys

from ymal import settings, similarity, tuning

OUT_DIR = settings.DATA_DIR / "phase3"


def load_units() -> dict:
    """
    Units sold per product, written by build_blocks while it was already
    counting them.

    Optional. Without it every product scores as equally popular and the pools
    are content-only, so this works before build_blocks has ever run - it just
    says so rather than failing.
    """
    path = settings.DATA_DIR / "blocks" / "units.json"
    if not path.exists():
        print("  units.json not found - pools will be content-only.")
        print("  Run `python -m scripts.build_blocks` first to include sales.")
        return {}, None
    data = json.loads(path.read_text())
    # by_style is written by build_blocks. Absent on a units.json from before
    # 2026-09-12, in which case build_pools derives it from the eligible rows
    # and simply misses sold-out colorways.
    return data["units"], data.get("by_style")


def load_features() -> list[dict]:
    path = settings.DATA_DIR / "phase2" / "features.json"
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Run `python -m scripts.build_features` first."
        )
    return json.loads(path.read_text())


def show_one(rows: list[dict], pools: dict, title: str) -> None:
    """Print one anchor's pool, for eyeballing whether it looks sensible."""
    match = next((r for r in rows if r["title"].lower() == title.lower()), None)
    if match is None:
        raise SystemExit(f"No eligible product titled {title!r}.")

    print(f"\n{match['title']}  ({match['season']}, "
          f"{match['product_type_normalised']})")
    print("-" * 68)
    for item in pools[match["product_id"]][:12]:
        print(f"  {item['score']:>6.3f}  {item['title']}")


def main() -> None:
    # Before anything reads a weight. The console's saved tuning overrides
    # settings.py for this run; with nothing saved, or with Shopify
    # unreachable, the defaults in settings.py are used and it says so.
    changed = tuning.load_and_apply()
    print(f"  {tuning.describe(changed)}")

    rows = load_features()
    print(f"Eligible products: {len(rows)}")

    units, style_units = load_units()
    if units:
        print(f"  sales for {len(units)} products, best seller "
              f"{max(units.values())} units")

    pools = similarity.build_pools(rows, units=units, style_units=style_units)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "pools.json"
    out.write_text(
        json.dumps(
            {
                "depth": settings.POOL_DEPTH,
                "require_same_season": settings.REQUIRE_SAME_SEASON,
                "weights": settings.SIMILARITY_WEIGHTS,
                # Recorded so a pool file can be read back against the
                # settings that produced it. Without this, "why does this look
                # different from yesterday" has no answer on disk.
                "popularity_weight": settings.POPULARITY_WEIGHT,
                "idf_power": settings.IDF_POWER,
                "tuning_overrides": changed,
                "pools": pools,
            },
            indent=2,
        )
    )

    sizes = [len(p) for p in pools.values()]
    empty = sum(1 for s in sizes if s == 0)
    thin = sum(1 for s in sizes if 0 < s < 6)

    print("\n" + "=" * 52)
    print("PHASE 3 — CANDIDATE POOLS")
    print("=" * 52)
    print(f"  anchors         : {len(pools)}")
    print(f"  target depth    : {settings.POOL_DEPTH}")
    print(f"  pool size       : min {min(sizes)}, median "
          f"{int(statistics.median(sizes))}, max {max(sizes)}")
    print(f"  empty pools     : {empty}")
    print(f"  thin (under 6)  : {thin}")
    print(f"  popularity      : {'on' if units else 'off (no units.json)'}")
    print(f"  {tuning.describe(changed)}")
    print(f"\n  -> {out}")

    if "--show" in sys.argv:
        show_one(rows, pools, sys.argv[sys.argv.index("--show") + 1])

    problems = similarity.check(rows, pools)
    print("\n" + "-" * 52)
    if problems:
        print("  FAILED SELF-CHECK - do not publish these pools:")
        for problem in problems:
            print(f"    {problem}")
    else:
        print("  OK: self-check passed. Every pool is eligible-only, one")
        print("      product per style, same season, never its own style.")
    print("-" * 52)


if __name__ == "__main__":
    main()
