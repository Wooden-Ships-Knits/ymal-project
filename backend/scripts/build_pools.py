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

from ymal import settings, similarity

OUT_DIR = settings.DATA_DIR / "phase3"


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
    rows = load_features()
    print(f"Eligible products: {len(rows)}")

    pools = similarity.build_pools(rows)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "pools.json"
    out.write_text(
        json.dumps(
            {
                "depth": settings.POOL_DEPTH,
                "require_same_season": settings.REQUIRE_SAME_SEASON,
                "weights": settings.SIMILARITY_WEIGHTS,
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
