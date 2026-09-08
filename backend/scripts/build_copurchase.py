"""
Phase 4 — blend co-purchase into the candidate pools.

Learns "customers who bought this also bought" from a year of orders, then
reorders each content pool by it. Membership never changes, so the season,
eligibility and colorway rules from Phase 3 always hold.

Also runs the offline evaluation that decides whether this is worth shipping:
if reranking does not beat content alone on held-out orders, it says so.

Run:  cd backend && python -m scripts.build_copurchase
      cd backend && python -m scripts.build_copurchase --show "GAME DAY V COTTON"
Output -> backend/data/phase4/pools_reranked.json, evaluation.json
"""

import json
import sys

from ymal import copurchase, evaluate, settings
from ymal.orders import baskets

OUT_DIR = settings.DATA_DIR / "phase4"


def load(path, hint):
    if not path.exists():
        raise SystemExit(f"{path} not found. Run `{hint}` first.")
    return json.loads(path.read_text())


def show_one(rows, before, after, title):
    match = next((r for r in rows if r["title"].lower() == title.lower()), None)
    if match is None:
        raise SystemExit(f"No eligible product titled {title!r}.")

    pid = match["product_id"]
    was = {c["product_id"]: i + 1 for i, c in enumerate(before[pid])}

    print(f"\n{match['title']}  — after reranking")
    print("-" * 72)
    for new_rank, item in enumerate(after[pid][:12], start=1):
        old_rank = was[item["product_id"]]
        move = old_rank - new_rank
        arrow = f"  ({move:+d})" if move else ""
        print(f"  {new_rank:>2}. {item['final_score']:>6.3f}  "
              f"lift {item['copurchase_lift']:>5.2f}  {item['title']}{arrow}")


def main() -> None:
    rows = load(
        settings.DATA_DIR / "phase2" / "features.json", "python -m scripts.build_features"
    )
    pools_doc = load(
        settings.DATA_DIR / "phase3" / "pools.json", "python -m scripts.build_pools"
    )
    pools = pools_doc["pools"]

    print(f"Fetching {settings.COPURCHASE_WINDOW_DAYS} days of orders...")
    all_baskets, report = baskets(settings.COPURCHASE_WINDOW_DAYS)
    print(f"  {report['orders']:,} orders, "
          f"{report['multi_item_orders']:,} with more than one product")

    if report["truncated_orders"]:
        print(f"  WARNING: {report['truncated_orders']} order(s) hit the line-item")
        print("           page size - their baskets are incomplete.")

    style_of = {r["product_gid"]: r["style_key"] for r in rows}
    scores = copurchase.build_scores(all_baskets, style_of)
    reranked = copurchase.rerank_pools(pools, rows, scores)

    print("\nEvaluating against held-out orders...")
    result = evaluate.compare(pools, rows, all_baskets, k=6)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "pools_reranked.json").write_text(
        json.dumps({**pools_doc, "pools": reranked,
                    "copurchase_window_days": settings.COPURCHASE_WINDOW_DAYS}, indent=2)
    )
    (OUT_DIR / "evaluation.json").write_text(json.dumps(result, indent=2))

    print("\n" + "=" * 56)
    print("PHASE 4 — CO-PURCHASE")
    print("=" * 56)
    print(f"  baskets used        : {len([b for b in all_baskets if b]):,}")
    print(f"  styles seen         : {len(scores['singles'])}")
    print(f"  pairs above floor   : "
          f"{sum(1 for c in scores['pairs'].values() if c >= settings.COPURCHASE_MIN_PAIRS):,}")
    print()
    print(f"  evaluation at k={result['k']} (the widget slot count)")
    print(f"    train baskets     : {result['train_baskets']:,}")
    print(f"    test baskets      : {result['test_baskets']:,}")
    print(f"    questions asked   : {result['content_only']['questions']:,}")
    print(f"    content only      : {result['content_only']['hit_rate']:.4f}")
    print(f"    with co-purchase  : {result['reranked']['hit_rate']:.4f}")
    print(f"    delta             : {result['delta']:+.4f}")

    if "--show" in sys.argv:
        show_one(rows, pools, reranked, sys.argv[sys.argv.index("--show") + 1])

    problems = copurchase.check(pools, reranked)
    print("\n" + "-" * 56)
    if problems:
        print("  FAILED SELF-CHECK - reranking changed pool membership:")
        for problem in problems:
            print(f"    {problem}")
    elif not result["improved"]:
        print("  DOES NOT BEAT CONTENT ALONE. Do not ship this - Phase 4's")
        print("  exit criterion is not met. The pools are unchanged in")
        print("  membership, so Phase 3 output remains usable as-is.")
    else:
        print("  OK: membership unchanged, and reranking beats content alone")
        print("      on held-out orders.")
    print("-" * 56)


if __name__ == "__main__":
    main()
