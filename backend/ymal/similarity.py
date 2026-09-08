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


def split_facets(tags: set[str]) -> dict[str, set[str]]:
    """Bucket a product's tags by facet. Tags matching none are dropped."""
    buckets: dict[str, set[str]] = {f: set() for f in settings.SIMILARITY_FACETS}
    for tag in tags:
        facet = facet_of(tag)
        if facet:
            buckets[facet].add(tag)
    return buckets


def inverse_document_frequency(
    tag_sets: list[set[str]],
) -> dict[str, float]:
    """
    How much each tag says about a product.

    A tag on half the catalog barely distinguishes anything; one on 18% says a
    lot. Standard IDF, smoothed so a tag on every product scores near zero
    rather than exactly zero.
    """
    total = len(tag_sets) or 1
    counts: dict[str, int] = {}
    for tags in tag_sets:
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
    return {tag: math.log(total / (1 + count)) + 1.0 for tag, count in counts.items()}


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


def score(anchor: dict, candidate: dict, idf: dict[str, float]) -> float:
    """
    How related two products are. Higher is more related.

    Comparable within one anchor's pool, which is all ranking needs - it is not
    a probability and should not be read as one.
    """
    total = 0.0

    for facet, weight in settings.SIMILARITY_WEIGHTS.items():
        if facet == "silhouette":
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
    Attach normalised facet tag sets to each row, and compute IDF once.

    Done up front because both are shared across every anchor - recomputing
    per anchor would be 258 times the work for the same answer.
    """
    vocabulary = build_vocabulary([r["signal_tags"] for r in rows])

    prepared = []
    for row in rows:
        tags = normalise_tags(row["signal_tags"], vocabulary)
        prepared.append({**row, "_tags": tags, "_facets": split_facets(tags)})

    idf = inverse_document_frequency([r["_tags"] for r in prepared])
    return prepared, idf


def build_pool(anchor: dict, candidates: list[dict], idf: dict, depth: int) -> list[dict]:
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

        value = score(anchor, candidate, idf)
        if value <= 0:
            continue

        current = best_by_style.get(candidate["style_key"])
        if current is None or value > current["score"]:
            best_by_style[candidate["style_key"]] = {
                "product_id": candidate["product_id"],
                "handle": candidate["handle"],
                "title": candidate["title"],
                "style_key": candidate["style_key"],
                "score": round(value, 4),
            }

    ranked = sorted(
        best_by_style.values(), key=lambda item: (-item["score"], item["product_id"])
    )
    return ranked[:depth]


def build_pools(rows: list[dict], depth: int | None = None) -> dict[str, list[dict]]:
    """Every eligible product's pool, keyed by product_id."""
    depth = depth or settings.POOL_DEPTH
    prepared, idf = prepare(rows)
    return {
        anchor["product_id"]: build_pool(anchor, prepared, idf, depth)
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
