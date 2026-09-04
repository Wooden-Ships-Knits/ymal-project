"""
Trending — RISING, not raw volume.

Decided 2026-09-04. Ranking the last 14 days by units sold returns nearly the
same products as ranking the last 90, and two blocks showing one list looks
broken to a shopper. So Trending answers a different question: what is selling
*more than it was*.

    score = (units_now + k) / (units_before + k)

The smoothing constant k does two jobs: it stops a product with no prior sales
scoring infinity, and it damps small numbers generally, so 1 -> 3 units does not
outrank 40 -> 90.

A minimum on units_now keeps noise out entirely — without it the list fills with
products that sold twice.

Pure functions, no I/O, so the ranking can be tested against known counters
without touching Shopify.
"""

from collections import Counter

from ymal import settings


def rising_score(units_now: int, units_before: int, smoothing: float | None = None) -> float:
    """Growth ratio, smoothed. 1.0 means flat; below 1.0 means declining."""
    k = settings.TRENDING_SMOOTHING if smoothing is None else smoothing
    return (units_now + k) / (units_before + k)


def rank(
    units_now: Counter,
    units_before: Counter,
    eligible: set[str] | None = None,
    min_units: int | None = None,
    limit: int | None = None,
    dedupe_by: dict[str, str] | None = None,
) -> list[dict]:
    """
    Rank products by how much their sales are rising.

    `eligible` filters BEFORE ranking, not after — ranking then truncating would
    let the gate hollow out a list that already looked full. Markdown sells
    fastest, so the raw top of a sales ranking is exactly what the gate removes.

    `dedupe_by` maps product GID -> a style key, and keeps only the best-scoring
    product per key. Half this catalog is a repeat colorway (124 distinct titles
    across 253 eligible products), and a trending style trends in every colour
    at once — so without this the block shows the same sweater three times and
    a list stored 30 deep holds barely 15 styles.

    Deduping here rather than at render time is deliberate: colorway grouping is
    slow-changing and identical for every shopper, so it belongs in the nightly
    build. Only the checks that depend on live state — stock, publication — need
    to happen at render.

    Ties on score are broken by absolute volume, so among two products growing
    equally the busier one wins.
    """
    floor = settings.TRENDING_MIN_UNITS if min_units is None else min_units
    depth = settings.STORED_LIST_DEPTH if limit is None else limit

    rows = []
    for gid, now in units_now.items():
        if eligible is not None and gid not in eligible:
            continue
        if now < floor:
            continue
        before = units_before.get(gid, 0)
        rows.append({
            "product_gid": gid,
            "units_now": now,
            "units_before": before,
            "score": round(rising_score(now, before), 4),
        })

    rows.sort(key=lambda r: (-r["score"], -r["units_now"]))

    if dedupe_by is not None:
        seen: set[str] = set()
        deduped = []
        for row in rows:
            key = dedupe_by.get(row["product_gid"], row["product_gid"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        rows = deduped

    return rows[:depth]
