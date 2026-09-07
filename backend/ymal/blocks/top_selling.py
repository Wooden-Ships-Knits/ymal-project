"""
Top Selling — plain volume over a long window.

The counterpart to Trending. Trending asks what is selling MORE than it was;
this asks what simply sells. Same extract, one window argument apart, which is
why the ranking lives in its own small module rather than a second copy of the
order code.

Pure functions, no I/O.
"""

from collections import Counter

from ymal import settings


def rank(
    units: Counter,
    eligible: set[str] | None = None,
    limit: int | None = None,
    dedupe_by: dict[str, str] | None = None,
) -> list[dict]:
    """
    Rank by units sold, filtered to eligible products first.

    Filtering before ranking matters more here than anywhere else in the
    project: markdown sells fastest, so the raw top of a volume ranking is
    exactly what the *SALE* rule removes. Rank first and the list arrives
    hollowed out.
    """
    depth = settings.STORED_LIST_DEPTH if limit is None else limit

    rows = [
        {"product_gid": gid, "units": sold}
        for gid, sold in units.items()
        if eligible is None or gid in eligible
    ]
    rows.sort(key=lambda r: -r["units"])

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
