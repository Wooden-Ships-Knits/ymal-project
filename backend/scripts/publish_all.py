"""
Phase 5 — the nightly publish.

Writes everything the theme reads: the eligibility flag and the recommendation
pool on each product, and the three store-wide block lists on the shop.

Idempotent. Running it twice writes the same values and reports zero churn,
which is what makes it safe to put on a schedule.

Reads what the earlier phases produced on disk. It computes nothing itself -
a bad run can therefore be read in data/ before it ever reaches Shopify.

Run:  cd backend && python -m scripts.publish_all --dry-run
      cd backend && python -m scripts.publish_all
Output -> backend/data/phase5/run_report.json, last_published.json
"""

import json
import sys

from ymal import publish, settings

OUT_DIR = settings.DATA_DIR / "phase5"
SNAPSHOT = OUT_DIR / "last_published.json"

# A pool thinner than this cannot fill a widget once the render-time gate,
# the anchor exclusion and the colorway dedupe have taken their cut.
MIN_POOL_DEPTH = 6


def load(path, hint):
    if not path.exists():
        raise SystemExit(f"{path} not found. Run `{hint}` first.")
    return json.loads(path.read_text())


def load_pools() -> dict:
    """Prefer the reranked pools; fall back to content-only if Phase 4 has not run."""
    reranked = settings.DATA_DIR / "phase4" / "pools_reranked.json"
    if reranked.exists():
        return json.loads(reranked.read_text())["pools"]
    return load(
        settings.DATA_DIR / "phase3" / "pools.json", "python -m scripts.build_pools"
    )["pools"]


def load_block_lists() -> dict[str, list[str]]:
    """The three store-wide lists, as product GIDs in rank order."""
    blocks = {}
    for key in publish.BLOCK_KEYS:
        path = settings.DATA_DIR / "blocks" / f"{key}.json"
        if not path.exists():
            print(f"  WARNING: {path.name} missing - skipping {key}")
            continue
        payload = json.loads(path.read_text())
        blocks[key] = [item["product_gid"] for item in payload["items"]]
    return blocks


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    rows = load(
        settings.DATA_DIR / "phase2" / "features.json",
        "python -m scripts.build_features",
    )
    products = publish.load_products()
    pools = load_pools()
    blocks = load_block_lists()

    print(f"Eligible products : {len(rows)}")
    print(f"Pools             : {len(pools)}")
    print(f"Block lists       : {', '.join(blocks) or 'none'}")

    depths = [len(p) for p in pools.values()]
    thin = {pid: len(p) for pid, p in pools.items() if len(p) < MIN_POOL_DEPTH}

    previous = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}
    change = publish.churn(previous, pools)

    if dry_run:
        print("\nDRY RUN: nothing will be written.")

    created = []
    written = {"eligible": 0, "featured": 0, "blocks": 0}

    if not dry_run:
        print("\nEnsuring metafield definitions...")
        created = publish.ensure_definitions()
        print(f"  {len(created)} created, {5 - len(created)} already existed")

        print("Publishing eligibility...")
        written["eligible"] = publish.publish(products)["written"]

        print("Publishing pools...")
        written["featured"] = publish.write_metafields(
            publish.build_pool_metafields(pools, rows), "featured"
        )

        if blocks:
            print("Publishing block lists...")
            written["blocks"] = publish.write_metafields(
                publish.build_block_metafields(publish.shop_id(), blocks), "blocks"
            )

    report = {
        "products": len(products),
        "eligible": len(rows),
        "pools": len(pools),
        "pool_depth_min": min(depths) if depths else 0,
        "pool_depth_max": max(depths) if depths else 0,
        "below_minimum": thin,
        "block_lists": {k: len(v) for k, v in blocks.items()},
        "churn": change,
        "written": written,
        "definitions_created": created,
        "dry_run": dry_run,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "run_report.json").write_text(json.dumps(report, indent=2))
    if not dry_run:
        SNAPSHOT.write_text(json.dumps(pools))

    print("\n" + "=" * 56)
    print("PHASE 5 — PUBLISH")
    print("=" * 56)
    print(f"  pool depth        : min {report['pool_depth_min']}, "
          f"max {report['pool_depth_max']}")
    print(f"  below minimum {MIN_POOL_DEPTH}   : {len(thin)}")
    for key, count in report["block_lists"].items():
        print(f"  {key:<18}: {count} products")
    print()
    print("  churn vs last run:")
    if change["comparable"]:
        print(f"    pools compared    {change['comparable']}")
        print(f"    unchanged         {change['unchanged']}")
        print(f"    mean replaced     {change['mean_replaced_pct']}%")
        print(f"    over half changed {change['churned_over_half']}")
    else:
        print("    no previous run to compare against")

    if not dry_run:
        print()
        print(f"  written: {written['eligible']} eligible, "
              f"{written['featured']} pools, {written['blocks']} block lists")

    print("\n" + "-" * 56)
    if thin:
        print(f"  FAILED: {len(thin)} product(s) below the minimum pool depth")
        print("  of {}. Phase 5's exit criterion is not met.".format(MIN_POOL_DEPTH))
    elif dry_run:
        print("  Nothing written. Re-run without --dry-run to publish.")
    else:
        print("  OK: full catalog published, every pool at or above the")
        print(f"      minimum depth of {MIN_POOL_DEPTH}.")
    print("-" * 56)


if __name__ == "__main__":
    main()
