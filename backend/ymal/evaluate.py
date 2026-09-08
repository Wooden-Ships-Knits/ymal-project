"""
Offline evaluation — does co-purchase reranking actually beat content alone?

Phase 4's exit criterion. The method: hold out the most recent slice of
baskets, learn co-purchase from the rest, then ask which ranking puts genuine
co-purchases nearer the top of the pool.

Held out by RECENCY rather than at random, because that is the real task -
predicting what will be bought together next, using what was bought together
before. A random split leaks the future into the training set and flatters the
result.

Pure functions, no I/O.
"""

from ymal import copurchase


def split_by_recency(baskets: list[set], holdout_fraction: float = 0.1) -> tuple:
    """
    Split baskets into (train, test), test being the most recent.

    Assumes baskets arrive newest-first, which is what the Shopify orders query
    returns. The most recent slice is held out.
    """
    if not baskets:
        return [], []
    size = max(1, int(len(baskets) * holdout_fraction))
    return baskets[size:], baskets[:size]


def hit_rate_at_k(pools: dict, test_styles: list[set], style_of: dict, k: int) -> dict:
    """
    Of the styles genuinely bought with an anchor, how many were in its top k?

    One "question" per (anchor, co-bought style) pair in the held-out baskets.
    A pair we could never answer - because the anchor has no pool - is counted
    as unanswerable rather than as a miss, so the two rankings are compared on
    the same questions.
    """
    style_to_anchor: dict[str, list[str]] = {}
    for pid, style in style_of.items():
        style_to_anchor.setdefault(style, []).append(pid)

    hits = 0
    asked = 0
    unanswerable = 0

    for basket in test_styles:
        for anchor_style in basket:
            others = basket - {anchor_style}
            if not others:
                continue

            anchors = style_to_anchor.get(anchor_style, [])
            if not anchors:
                unanswerable += len(others)
                continue

            pool = pools.get(anchors[0], [])
            if not pool:
                unanswerable += len(others)
                continue

            top = {c["style_key"] for c in pool[:k]}
            for other in others:
                asked += 1
                if other in top:
                    hits += 1

    return {
        "k": k,
        "questions": asked,
        "hits": hits,
        "hit_rate": round(hits / asked, 4) if asked else 0.0,
        "unanswerable": unanswerable,
    }


def compare(
    pools: dict,
    rows: list[dict],
    baskets: list[set],
    holdout_fraction: float = 0.1,
    k: int = 6,
) -> dict:
    """
    Content-only versus co-purchase-reranked, on the same held-out questions.

    `k` defaults to 6 because that is the widget slot count - the question that
    matters is what a shopper actually sees, not what sits at rank 25.
    """
    style_of = {r["product_gid"]: r["style_key"] for r in rows}
    style_of_id = {r["product_id"]: r["style_key"] for r in rows}

    train, test = split_by_recency(baskets, holdout_fraction)

    train_styles = copurchase.style_baskets(train, style_of)
    test_styles = copurchase.style_baskets(test, style_of)

    scores = copurchase.build_scores(train, style_of)
    reranked = copurchase.rerank_pools(pools, rows, scores)

    content = hit_rate_at_k(pools, test_styles, style_of_id, k)
    blended = hit_rate_at_k(reranked, test_styles, style_of_id, k)

    delta = blended["hit_rate"] - content["hit_rate"]
    return {
        "train_baskets": len(train_styles),
        "test_baskets": len(test_styles),
        "k": k,
        "content_only": content,
        "reranked": blended,
        "delta": round(delta, 4),
        "improved": delta > 0,
    }
