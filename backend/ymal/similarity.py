"""
Content-based similarity — docs/logic.md sections 1-3.

Two products are related when they share what a shopper actually looks at:
motif, fabric and weight, colour family, and silhouette. Agreed 2026-09-08 and
recorded in caveats.md section 6; the weights and facet definitions live in
settings.py so they can be retuned without touching this file.

Pure functions, no I/O. A wrong score is invisible until a customer sees a bad
recommendation, so the scoring has to be checkable against known inputs.

Nothing here reads or applies eligibility. Pools are built from the Phase 2
table, which contains eligible products only.
"""

import math

from ymal import settings


def normalise_tag(tag: str) -> str:
    """Lowercase and trim. The cheap half of tag normalisation."""
    return (tag or "").strip().lower()


def build_vocabulary(tag_lists: list[list[str]]) -> set[str]:
    """Every normalised tag in the catalog."""
    return {normalise_tag(t) for tags in tag_lists for t in tags if normalise_tag(t)}


def depluralise(tag: str, vocabulary: set[str]) -> str:
    """
    Collapse a plural onto its singular, but only when the singular is really
    a tag in this catalog.

    This catalog carries stripe/stripes, graphic/graphics, football/footballs
    and word/words as separate tags. Left alone they double-count: two products
    sharing "stripe" AND "stripes" look twice as similar as they are.

    Checking the vocabulary rather than stripping every trailing "s" avoids
    mangling words that simply end in one.
    """
    if tag.endswith("s") and tag[:-1] in vocabulary:
        return tag[:-1]
    return tag


def normalise_tags(tags: list[str], vocabulary: set[str]) -> set[str]:
    """Normalised, de-pluralised, de-duplicated."""
    return {
        depluralise(normalise_tag(t), vocabulary)
        for t in tags
        if normalise_tag(t)
    }


# A collection on nearly every product says nothing about any of them. This
# shop's 23 collections include testimonial, cloud-search-all-products,
# tax-clothing and discount-applicable-* on 88-100% of the catalog.
#
# IDF alone does NOT handle these: the formula carries a +1.0 floor, so a
# collection on 100% of products still scores 0.82 against 1.92 for a rare one.
# With six such collections on every product they would dominate the overlap
# and make every pair look related. They are removed outright instead.
NEAR_UNIVERSAL_COLLECTIONS = 0.6


def signal_collections(
    handles: set[str], frequency: dict[str, int], total: int
) -> set[str]:
    """The collections that can actually tell two products apart."""
    return {
        h for h in handles
        if frequency.get(h, 0) < total * NEAR_UNIVERSAL_COLLECTIONS
    }


def facet_of(tag: str) -> str | None:
    """
    Which facet a tag belongs to, or None.

    Substring matching, because this catalog writes "chunky blend", "chunky
    tag" and "chunky-vo" for one idea. A tag matching more than one facet takes
    the first in settings order - deliberate, so "cotton blend" counts as
    fabric rather than being split.
    """
    for facet, keywords in settings.SIMILARITY_FACETS.items():
        if any(keyword in tag for keyword in keywords):
            return facet
    return None


# Tags claimed by no named facet go here rather than being discarded.
OTHER_FACET = "other"


def split_facets(tags: set[str]) -> dict[str, set[str]]:
    """
    Bucket a product's tags by facet.

    Nothing is dropped. A tag matching no keyword goes to `other`, which is
    where the theme and occasion vocabulary lives - halloween, spooky,
    tailgate, superbowl - along with cut and release tags.

    Discarding them was a real defect: the named facets kept 33% of the signal
    tags and threw away the rest, so a pumpkin sweater's "halloween" and
    "spooky" counted for nothing and it matched every other black graphic
    sweater on the single word they shared.

    IDF still decides how much each one is worth, so a rare "spooky season"
    weighs heavily and a common "autumn" barely at all - no keyword list to
    maintain.
    """
    buckets: dict[str, set[str]] = {f: set() for f in settings.SIMILARITY_FACETS}
    buckets.setdefault(OTHER_FACET, set())
    for tag in tags:
        buckets[facet_of(tag) or OTHER_FACET].add(tag)
    return buckets


def inverse_document_frequency(
    tag_sets: list[set[str]],
) -> dict[str, float]:
    """
    How much each tag says about a product.

    No smoothing floor. An earlier version added 1.0 to every score, which left
    a tag on the whole catalog worth 0.82 against 1.92 for a rare one - only a
    2.3x gap. Two products then matched on the twenty generic tags every
    sweater carries, and a single telling tag like "pumpkin" could not outweigh
    them. Without the floor a universal tag is worth nothing, which is the
    truth about it.

    Raised to IDF_POWER on top, so the gap between a rare tag and a common one
    widens further. At 2.0 a tag on 2% of the catalog is worth roughly thirty
    times one on half of it.
    """
    total = len(tag_sets) or 1
    counts: dict[str, int] = {}
    for tags in tag_sets:
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
    return {
        tag: max(math.log(total / (1 + count)), 0.0) ** settings.IDF_POWER
        for tag, count in counts.items()
    }


def weighted_jaccard(a: set[str], b: set[str], idf: dict[str, float]) -> float:
    """
    Overlap of two tag sets, weighted by how informative each tag is.

    Plain Jaccard treats "football" and "cotton" as equally meaningful. They
    are not: nearly everything is cotton.
    """
    if not a and not b:
        return 0.0
    shared = a & b
    union = a | b
    if not union:
        return 0.0
    numerator = sum(idf.get(t, 1.0) for t in shared)
    denominator = sum(idf.get(t, 1.0) for t in union)
    return numerator / denominator if denominator else 0.0


def score(
    anchor: dict,
    candidate: dict,
    idf: dict[str, float],
    collection_idf: dict[str, float] | None = None,
) -> float:
    """
    How related two products are. Higher is more related.

    Comparable within one anchor's pool, which is all ranking needs - it is not
    a probability and should not be read as one.
    """
    total = 0.0

    for facet, weight in settings.SIMILARITY_WEIGHTS.items():
        if facet == OTHER_FACET:
            total += weight * weighted_jaccard(
                anchor["_facets"].get(OTHER_FACET, set()),
                candidate["_facets"].get(OTHER_FACET, set()),
                idf,
            )
        elif facet == "collection":
            # Collections have their own IDF, computed over collection
            # membership rather than tags: "cottons" as a collection and
            # "cottons" as a tag are different populations and would weigh each
            # other wrongly if pooled.
            total += weight * weighted_jaccard(
                anchor["_collections"], candidate["_collections"], collection_idf or {}
            )
        elif facet == "silhouette":
            same = (
                anchor["product_type_normalised"]
                and anchor["product_type_normalised"]
                == candidate["product_type_normalised"]
            )
            total += weight * (1.0 if same else 0.0)
        else:
            total += weight * weighted_jaccard(
                anchor["_facets"][facet], candidate["_facets"][facet], idf
            )

    return total


def season_allows(anchor: dict, candidate: dict) -> bool:
    """
    The season rule. Hard filter, not a score - decided 2026-09-08.

    A product with no season would otherwise match nothing, so it ignores the
    rule rather than shipping an empty pool.
    """
    if not settings.REQUIRE_SAME_SEASON:
        return True
    if not anchor["season"]:
        return settings.SEASONLESS_IGNORES_SEASON
    return anchor["season"] == candidate["season"]


def prepare(rows: list[dict]) -> tuple[list[dict], dict[str, float]]:
    """
    Attach the facet tag sets and collections to each row, and compute both
    IDF tables once.

    Done up front because both are shared across every anchor - recomputing
    per anchor would be 258 times the work for the same answer.
    """
    vocabulary = build_vocabulary([r["signal_tags"] for r in rows])

    raw_collections = [
        {c.strip().lower() for c in row.get("collections", []) if c} for row in rows
    ]
    frequency: dict[str, int] = {}
    for handles in raw_collections:
        for handle in handles:
            frequency[handle] = frequency.get(handle, 0) + 1

    prepared = []
    for row, handles in zip(rows, raw_collections):
        tags = normalise_tags(row["signal_tags"], vocabulary)
        prepared.append({
            **row,
            "_tags": tags,
            "_facets": split_facets(tags),
            "_collections": signal_collections(handles, frequency, len(rows)),
        })

    idf = inverse_document_frequency([r["_tags"] for r in prepared])
    collection_idf = inverse_document_frequency([r["_collections"] for r in prepared])
    return prepared, idf, collection_idf


def style_of(row: dict) -> str:
    """
    The key a style's sales are counted under.

    build_blocks keys its map on TITLE.strip().upper() while features.json
    keeps the title exactly as Shopify has it, so both sides normalise here.
    """
    return (row.get("style_key") or "").strip().upper()


def units_by_style(rows: list[dict], units: dict) -> dict[str, int]:
    """
    Units summed across every colorway of each style.

    A pool row IS a style - build_pool keeps one product per style_key and
    shows the best-scoring colorway - so the sales figure beside it has to be
    the style's. Counting a single colorway meant a sweater selling 38 units
    across twelve colorways scored as though it had sold 9. On this catalog 18
    of 128 styles understated by 2x or more.

    Built from the eligible rows, which is also what keeps the SCALE honest.
    The raw units table is topped by things no pool can ever contain - a
    product that is not even active at 499 units, and "Front & Back Placement
    Add-on", a service line, at 119. Dividing every garment by 499 squashed the
    entire popularity column into the bottom third of its range.

    *SALE* colorways drop out for free: their title carries the marker, so they
    are a different style_key. That is correct - markdown volume is not
    evidence of full-price demand.
    """
    totals: dict[str, int] = {}
    if not units:
        return totals
    for row in rows:
        sold = units.get(row["product_gid"], 0)
        if sold:
            totals[style_of(row)] = totals.get(style_of(row), 0) + sold
    return totals


def popularity(totals: dict, style_key: str, most: int) -> float:
    """
    How well this STYLE sells, as 0-1 against the best-selling style that could
    actually be recommended.

    Square-rooted so the scale is not owned by its extremes: the top style
    sells 318 units in a fortnight while most sell single digits, and a linear
    scale would leave every other style indistinguishable at nearly zero.
    """
    if most <= 0:
        return 0.0
    return (max(totals.get(style_key, 0), 0) / most) ** 0.5


def build_pool(
    anchor: dict,
    candidates: list[dict],
    idf: dict,
    depth: int,
    collection_idf: dict | None = None,
    units: dict | None = None,
    most_units: int = 0,
) -> list[dict]:
    """
    The ranked candidate pool for one product.

    Applies the hard rules, then ranks. One product per style_key: a pool full
    of one sweater in eight colours is not a recommendation.
    """
    best_by_style: dict[str, dict] = {}

    for candidate in candidates:
        if candidate["product_id"] == anchor["product_id"]:
            continue
        # Never the anchor's own style - those are its colorways, and the
        # widget is meant to show something else.
        if candidate["style_key"] == anchor["style_key"]:
            continue
        if not season_allows(anchor, candidate):
            continue

        content = score(anchor, candidate, idf, collection_idf)
        if content <= 0:
            continue

        # Popularity reorders within the pool; it never decides membership.
        # A product that is not similar enough to be here does not get in by
        # selling well.
        sells = popularity(units or {}, style_of(candidate), most_units)
        value = content * (1 + settings.POPULARITY_WEIGHT * sells)

        current = best_by_style.get(candidate["style_key"])
        if current is None or value > current["score"]:
            best_by_style[candidate["style_key"]] = {
                "product_id": candidate["product_id"],
                "handle": candidate["handle"],
                "title": candidate["title"],
                "style_key": candidate["style_key"],
                "score": round(value, 4),
                "content_score": round(content, 4),
                "popularity": round(sells, 3),
            }

    ranked = sorted(
        best_by_style.values(), key=lambda item: (-item["score"], item["product_id"])
    )
    return ranked[:depth]


def build_pools(
    rows: list[dict],
    depth: int | None = None,
    units: dict | None = None,
    style_units: dict | None = None,
) -> dict[str, list[dict]]:
    """
    Every eligible product's pool, keyed by product_id.

    `units` is units sold per product gid, from data/blocks/units.json. Absent,
    every product scores as equally popular and the pools are content-only -
    so this still works before build_blocks has ever run.
    """
    depth = depth or settings.POOL_DEPTH
    prepared, idf, collection_idf = prepare(rows)

    # Per style, not per product, and scaled against the best style that can
    # actually appear in a pool. See units_by_style for why both halves matter.
    #
    # `style_units` comes from build_blocks, which can see every ACTIVE product
    # and so counts colorways that are currently sold out - real demand for the
    # style, even though that colorway cannot be shown today. Deriving from
    # `rows` is the fallback and misses exactly those.
    totals = style_units if style_units is not None else units_by_style(rows, units or {})

    # The denominator is the best style that can actually appear in a pool, so
    # a style with sales but no eligible colorway cannot set an unreachable top
    # of the scale.
    in_pool = {style_of(row) for row in rows}
    most_units = max((totals.get(s, 0) for s in in_pool), default=0)

    return {
        anchor["product_id"]: build_pool(
            anchor, prepared, idf, depth, collection_idf, totals, most_units
        )
        for anchor in prepared
    }


def check(rows: list[dict], pools: dict[str, list[dict]]) -> list[str]:
    """Self-check: assert the result, not the code that produced it."""
    problems = []
    by_id = {r["product_id"]: r for r in rows}
    eligible_ids = set(by_id)

    missing = [pid for pid in eligible_ids if not pools.get(pid)]
    if missing:
        problems.append(
            f"{len(missing)} product(s) have an empty pool, "
            f"e.g. {by_id[missing[0]]['title']!r}"
        )

    for pid, pool in pools.items():
        anchor = by_id[pid]

        outside = [c for c in pool if c["product_id"] not in eligible_ids]
        if outside:
            problems.append(f"{anchor['title']!r} recommends an ineligible product")
            break

        own = [c for c in pool if c["style_key"] == anchor["style_key"]]
        if own:
            problems.append(f"{anchor['title']!r} recommends its own style")
            break

        styles = [c["style_key"] for c in pool]
        if len(styles) != len(set(styles)):
            problems.append(f"{anchor['title']!r} has a repeated style in its pool")
            break

        if settings.REQUIRE_SAME_SEASON and anchor["season"]:
            wrong = [
                c for c in pool if by_id[c["product_id"]]["season"] != anchor["season"]
            ]
            if wrong:
                problems.append(
                    f"{anchor['title']!r} ({anchor['season']}) recommends a "
                    f"different season"
                )
                break

    return problems
