"""
The scheduled run — everything, in order, once a day.

Runs at 20:00 Makassar (12:00 UTC), which is early morning in the US: the
catalog has stopped changing for the day here, and the lists are refreshed
before the shopping day starts there.

STOPS ON THE FIRST FAILURE. A half-finished chain must not publish: pools built
from a stale product list are worse than yesterday's pools, because they look
current. If a step fails, Shopify keeps what it already has, which is a
coherent set from the last successful run.

Run:  cd backend && python -m scripts.nightly
      cd backend && python -m scripts.nightly --skip-copurchase
      cd backend && python -m scripts.nightly --dry-run
"""

import subprocess
import sys
import time
from datetime import datetime, timezone

# Order matters: each step reads what the one before it wrote.
STEPS = [
    ("fetch_products", "the eligible product list", []),
    ("build_features", "the feature table", []),
    # Blocks BEFORE pools: build_blocks counts units for Top Selling and
    # writes them out, and build_pools uses those to nudge similar products by
    # how well they sell. The other way round, pools would use yesterday's.
    ("build_blocks", "trending, top selling, new arrivals", []),
    ("build_pools", "content similarity pools", []),
    ("build_copurchase", "co-purchase reranking", []),
    ("publish_all", "write everything to Shopify", []),
    # Reads the cart attribute back off orders, so purchases can be
    # attributed. Last, because it reports on the storefront rather than
    # feeding anything the earlier steps need.
    ("attribute_orders", "attribute orders to the block that led to them", []),
]

# Pulling a year of orders is by far the slowest step, and co-purchase pairs
# barely move day to day. --skip-copurchase leaves the previous reranked pools
# in place; publish_all still finds and publishes them.
SLOW_STEPS = {"build_copurchase"}


def run(module: str, extra: list[str]) -> tuple[bool, float]:
    started = time.time()
    result = subprocess.run(
        [sys.executable, "-m", f"scripts.{module}", *extra],
        capture_output=True,
        text=True,
    )
    took = time.time() - started

    if result.returncode != 0:
        print(result.stdout[-3000:])
        print(result.stderr[-3000:], file=sys.stderr)
        return False, took

    # Surface the lines worth seeing in a log nobody reads unless something
    # looks wrong: warnings, failures, and each step's own OK line.
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith(("OK:", "WARNING:", "FAILED")):
            print(f"      {stripped}")

    return True, took


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    skip_slow = "--skip-copurchase" in sys.argv

    started = datetime.now(timezone.utc)
    print(f"YMAL nightly — {started.isoformat(timespec='seconds')}")
    print("=" * 58)

    steps = [s for s in STEPS if not (skip_slow and s[0] in SLOW_STEPS)]
    total = 0.0

    for index, (module, what, extra) in enumerate(steps, start=1):
        args = list(extra)
        if dry_run and module == "publish_all":
            args.append("--dry-run")

        label = f"[{index}/{len(steps)}] {module}"
        print(f"\n{label:<32} {what}")

        ok, took = run(module, args)
        total += took

        if not ok:
            print(f"\nFAILED at {module} after {total:.0f}s.")
            print("Nothing further ran. Shopify still holds the last complete")
            print("set, which is coherent - a partial chain is not.")
            raise SystemExit(1)

        print(f"      done in {took:.0f}s")

    print("\n" + "=" * 58)
    print(f"OK: {len(steps)} steps in {total:.0f}s"
          + (" (dry run, nothing written)" if dry_run else ""))


if __name__ == "__main__":
    main()
