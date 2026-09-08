"""
Co-purchase — "customers who bought this also bought" (Phase 4).

Counted at STYLE level, not product level. CHARLOTTE CREW COTTON has eleven
colorways; counting them separately splits one real signal eleven ways and
makes every pair look too rare to trust.

Scored by lift, not raw counts. Bestsellers appear in everything's basket, so
raw co-occurrence would just rediscover the top sellers under a different name.
Lift asks whether two styles sell together MORE than chance would predict.

Reranking only: content similarity decides who is in the pool, this decides the
order within it. A co-purchase pair can therefore never break the season,
eligibility or colorway rules.

Pure functions, no I/O.
"""

import itertools

from ymal import settings


def style_baskets(baskets: list[set], style_of: dict[str, str]) -> list[set]:
    """
    Rewrite product baskets as style baskets, dropping anything unknown.

    Products outside the eligible set are dropped rather than kept: a pair with
    something we would never recommend cannot inform a ranking of things we
    would.
    """
    out = []
    for basket in baskets:
        styles = {style_of[p] for p in basket if p in style_of}
        if len(styles) > 1:
            out.append(styles)
    return out


def count_pairs(baskets: list[set]) -> tuple[dict, dict, int]:
    """
    How often each style appears, how often each pair appears together, and
    how many baskets there were.

    Pairs are stored with the two style keys sorted, so a pair is counted once
    rather than once per direction.
    """
    singles: dict[str, int] = {}
    pairs: dict[tuple[str, str], int] = {}

    for basket in baskets:
        for style in basket:
            singles[style] = singles.get(style, 0) + 1
        for a, b in itertools.combinations(sorted(basket), 2):
            pairs[(a, b)] = pairs.get((a, b), 0) + 1

    return singles, pairs, len(baskets)


def lift(
    a: str,
    b: str,
    singles: dict[str, int],
    pairs: dict[tuple[str, str], int],
    total: int,
) -> float:
    """
    How much more often two styles are bought together than chance predicts.

    lift = P(a and b) / (P(a) * P(b))

    1.0 means exactly chance. Above 1 means a real association. Returns 0.0
    below the pair-count floor, where the number is dominated by coincidence.
    """
    if total <= 0:
        return 0.0

    key = (a, b) if a < b else (b, a)
    together = pairs.get(key, 0)
    if together < settings.COPURCHASE_MIN_PAIRS:
        return 0.0

    count_a = singles.get(a, 0)
    count_b = singles.get(b, 0)
    if not count_a or not count_b:
        return 0.0

    expected = (count_a / total) * (count_b / total)
    return (together / total) / expected if expected else 0.0


def build_scores(baskets: list[set], style_of: dict[str, str]) -> dict:
    """Everything reranking needs, computed once."""
    styles = style_baskets(baskets, style_of)
    singles, pairs, total = count_pairs(styles)
    return {"singles": singles, "pairs": pairs, "total": total}


def rerank(pool: list[dict], anchor_style: str, scores: dict) -> list[dict]:
    """
    Reorder one pool by co-purchase, keeping its membership unchanged.

    A candidate with no co-purchase history keeps its content score exactly —
    that is the cold-start path, and it is the permanent one for anything
    launched today, not a temporary gap.

    The boost is capped so a single strong pair cannot drag an otherwise
    unrelated product to the top of a pool it barely belongs in.
    """
    if not pool:
        return pool

    reranked = []
    for item in pool:
        value = lift(
            anchor_style,
            item["style_key"],
            scores["singles"],
            scores["pairs"],
            scores["total"],
        )
        # Anything at or below chance (lift <= 1) is not evidence of anything,
        # so it neither helps nor hurts.
        boost = max(0.0, min(value - 1.0, 1.0)) if value else 0.0
        reranked.append(
            {
                **item,
                "copurchase_lift": round(value, 3),
                "final_score": round(
                    item["score"] * (1 + settings.COPURCHASE_RERANK_WEIGHT * boost), 4
                ),
            }
        )

    return sorted(
        reranked, key=lambda i: (-i["final_score"], i["product_id"])
    )


def rerank_pools(pools: dict, rows: list[dict], scores: dict) -> dict:
    """Rerank every pool. Membership is untouched."""
    style_of_id = {r["product_id"]: r["style_key"] for r in rows}
    return {
        pid: rerank(pool, style_of_id[pid], scores)
        for pid, pool in pools.items()
    }


def check(before: dict, after: dict) -> list[str]:
    """
    Self-check: reranking must not change who is in a pool.

    That is the whole safety argument for this phase - if membership can
    change, the season and eligibility rules are no longer guaranteed.
    """
    problems = []

    if set(before) != set(after):
        problems.append("reranking added or removed an anchor")
        return problems

    for pid, pool in before.items():
        was = {c["product_id"] for c in pool}
        now = {c["product_id"] for c in after[pid]}
        if was != now:
            problems.append(
                f"pool membership changed for {pid}: "
                f"{len(was - now)} removed, {len(now - was)} added"
            )
            break
        if len(pool) != len(after[pid]):
            problems.append(f"pool length changed for {pid}")
            break

    return problems
