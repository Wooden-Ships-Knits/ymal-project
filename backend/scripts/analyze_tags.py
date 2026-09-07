"""
Does tag similarity actually work on this catalog?

The Featured block ranks products by how many tags they share with the anchor.
That only works if tags DISCRIMINATE — a tag carried by every product says
nothing. PPA writes 'sweater, sweaters, sweatshirt, outfit, outfits, casual'
onto everything, so plain overlap would rank close to random.

The fix is not machine learning, it is weighting: a tag's worth is inverse to
how many products carry it. This script measures whether that is enough, using
the real catalog rather than an assumption.

Run:  cd backend && python -m scripts.analyze_tags
      (reads data/phase1/active_products.json — run fetch_products first)
"""

import json
import math
from collections import Counter

from ymal import settings

# A tag on more than this share of the catalog is treated as noise in the
# report. It is a reporting threshold only — the scoring below needs no
# cutoff, because inverse weighting already drives those tags to ~zero.
NOISE_SHARE = 0.5

# How many neighbours to show per worked example.
TOP_N = 5


def load_eligible() -> list[dict]:
    path = settings.PHASE1_DIR / "active_products.json"
    rows = json.loads(path.read_text())
    return [r for r in rows if r["eligible"]]


def tag_list(row: dict) -> list[str]:
    return [t.strip() for t in (row.get("tags") or "").split(",") if t.strip()]


def idf_weights(products: list[dict]) -> tuple[Counter, dict[str, float]]:
    """Document frequency per tag, and the weight it earns."""
    df = Counter()
    for p in products:
        df.update(set(tag_list(p)))

    n = len(products)
    # log(N / df): a tag on every product scores exactly 0 and drops out on its
    # own — no stop-list to maintain as the catalog changes.
    weights = {tag: math.log(n / count) for tag, count in df.items()}
    return df, weights


def similarity(a: set[str], b: set[str], w: dict[str, float]) -> float:
    """Cosine similarity over inverse-weighted tag vectors."""
    shared = a & b
    if not shared:
        return 0.0
    num = sum(w[t] ** 2 for t in shared)
    na = math.sqrt(sum(w[t] ** 2 for t in a))
    nb = math.sqrt(sum(w[t] ** 2 for t in b))
    return num / (na * nb) if na and nb else 0.0


def main() -> None:
    products = load_eligible()
    if not products:
        raise SystemExit("No eligible products. Run `python -m scripts.fetch_products`.")

    df, weights = idf_weights(products)
    n = len(products)

    print("=" * 66)
    print("TAG DISCRIMINATION REPORT")
    print("=" * 66)
    print(f"  eligible products : {n}")
    print(f"  distinct tags     : {len(df)}")
    tags_per = [len(set(tag_list(p))) for p in products]
    print(f"  tags per product  : min {min(tags_per)}  median "
          f"{sorted(tags_per)[len(tags_per) // 2]}  max {max(tags_per)}")

    universal = [t for t, c in df.items() if c == n]
    noisy = [t for t, c in df.items() if c / n > NOISE_SHARE]
    once = [t for t, c in df.items() if c == 1]
    print(f"\n  on EVERY product  : {len(universal)}  -> weight exactly 0")
    print(f"  on >{int(NOISE_SHARE * 100)}% of products : {len(noisy)}")
    print(f"  on exactly one    : {len(once)}  -> useless too, nothing to share with")
    useful = [t for t, c in df.items() if 1 < c <= NOISE_SHARE * n]
    print(f"  actually useful   : {len(useful)}  (on 2..{int(NOISE_SHARE * n)} products)")

    print("\n  MOST COMMON TAGS")
    print(f"  {'tag':<28} {'products':>9} {'share':>7} {'weight':>8}")
    print("  " + "-" * 56)
    for tag, count in df.most_common(12):
        print(f"  {tag[:28]:<28} {count:>9} {count / n:>6.0%} {weights[tag]:>8.2f}")

    print("\n  MOST DISCRIMINATING TAGS  (shared by 2-20 products)")
    print("  " + "-" * 56)
    discriminating = sorted(
        ((t, c) for t, c in df.items() if 2 <= c <= 20),
        key=lambda kv: -weights[kv[0]],
    )[:12]
    for tag, count in discriminating:
        print(f"  {tag[:28]:<28} {count:>9} {count / n:>6.0%} {weights[tag]:>8.2f}")

    # ---- worked examples: does weighting change the answer?
    sets = {p["product_id"]: set(tag_list(p)) for p in products}
    titles = {p["product_id"]: p["title"] for p in products}

    print("\n" + "=" * 66)
    print("WORKED EXAMPLES — raw overlap vs weighted")
    print("=" * 66)

    for anchor in products[:3]:
        aid = anchor["product_id"]
        a = sets[aid]
        others = [p["product_id"] for p in products if p["product_id"] != aid]

        raw = sorted(others, key=lambda o: -len(a & sets[o]))[:TOP_N]
        weighted = sorted(others, key=lambda o: -similarity(a, sets[o], weights))[:TOP_N]

        print(f"\n  ANCHOR: {anchor['title']}")
        print(f"  {len(a)} tags\n")
        print(f"  {'by RAW shared-tag count':<42} | by WEIGHTED similarity")
        print("  " + "-" * 42 + "-+-" + "-" * 42)
        for i in range(TOP_N):
            left = f"{len(a & sets[raw[i]]):>2} shared  {titles[raw[i]][:30]}"
            score = similarity(a, sets[weighted[i]], weights)
            right = f"{score:>5.2f}     {titles[weighted[i]][:30]}"
            print(f"  {left:<42} | {right}")

    print("\n" + "=" * 66)
    print("READ THIS AS")
    print("=" * 66)
    if len(useful) < 20:
        print("  Too few discriminating tags. Tag overlap alone will not rank")
        print("  meaningfully - Featured needs product type and price band as guards.")
    else:
        print(f"  {len(useful)} tags carry real signal. Weighted overlap is enough to")
        print("  rank Featured; no model required. Guard with product type anyway.")
    print("  Note: the style tag is shared only by colorways of one style, so it")
    print("  scores highest of all - exclude it from scoring and use it for dedupe.")


if __name__ == "__main__":
    main()
