"""
The Phase 2 feature table — one row per eligible product, with everything
scoring needs.

Pure functions, no I/O, for the same reason eligibility.py is: content
similarity is built on these values, and a wrong feature is invisible until a
customer sees a bad recommendation.

Nothing here computes similarity. This produces the inputs; Phase 3 uses them.
"""

import statistics

# Tags on nearly every product cannot distinguish anything. `casual` is on all
# 258 eligible products, so two products sharing it are no more alike than two
# products picked at random - keeping it would add noise and cost.
#
# A fraction rather than a fixed list, so the cutoff follows the catalog
# instead of needing maintenance when the tagging changes.
NEAR_UNIVERSAL_CUTOFF = 0.9

# Tags on a single product cannot connect it to anything either. They are kept
# in the row (they may describe the product usefully) but excluded from
# signal_tags, which exists to be compared.
MIN_TAG_PRODUCTS = 2

# Shopify's storefront filter app writes these. They describe available sizes,
# not the garment, and every product carries the full set.
FILTER_TAG_PREFIX = "filterby-"

# This catalog uses both "autumn" and "fall". Same season, two spellings, so
# they are aliased rather than split - otherwise one product sits alone in a
# season of its own and matches nothing.
SEASON_ALIASES = {"fall": "autumn"}

SEASON_TAGS = ("spring", "summer", "autumn", "fall", "winter", "resort", "holiday")

# Measured on this catalog 2026-09-08: every eligible product falls between
# $137 and $159, a 16% spread, and prices cluster on a handful of values. The
# bands are therefore nearly meaningless here and price similarity should carry
# little or no weight in scoring. Kept because the spread may widen, and
# because "we checked and it does not help" is worth recording.
PRICE_BANDS = ("budget", "mid", "premium", "luxury")


def split_tags(raw: str) -> list[str]:
    """Shopify returns tags as one comma-separated string, not a list."""
    return [tag.strip() for tag in (raw or "").split(",") if tag.strip()]


def normalise_product_type(product_type: str) -> str:
    """
    Collapse the spellings of one type.

    This catalog carries V-Neck, V-neck and Vneck as three separate types, so
    42 products that are the same thing scatter across three buckets and any
    "same type" signal is diluted by two thirds.
    """
    return "".join(ch for ch in (product_type or "").lower() if ch.isalnum())


def tag_document_frequency(products: list[dict]) -> dict[str, int]:
    """How many products carry each tag."""
    counts: dict[str, int] = {}
    for product in products:
        for tag in set(split_tags(product.get("tags", ""))):
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def is_signal_tag(tag: str, count: int, total: int) -> bool:
    """Whether a tag can distinguish one product from another."""
    if tag.lower().startswith(FILTER_TAG_PREFIX):
        return False
    if count < MIN_TAG_PRODUCTS:
        return False
    return count < total * NEAR_UNIVERSAL_CUTOFF


def signal_tags(product: dict, frequency: dict[str, int], total: int) -> list[str]:
    """This product's tags, minus the ones that cannot distinguish it."""
    return sorted(
        tag
        for tag in set(split_tags(product.get("tags", "")))
        if is_signal_tag(tag, frequency.get(tag, 0), total)
    )


def season_of(product: dict) -> str | None:
    """The first season tag, or None. Seasons are tags, not a Shopify field."""
    lowered = {t.lower() for t in split_tags(product.get("tags", ""))}
    for season in SEASON_TAGS:
        if season in lowered:
            return SEASON_ALIASES.get(season, season)
    return None


def price_band_edges(prices: list[float]) -> list[float]:
    """
    Quartile cut points across the eligible catalog.

    Derived rather than hardcoded, so the bands stay meaningful when prices
    move. With too few distinct prices to form quartiles, returns [] and every
    product lands in one band - correct, and better than inventing boundaries.
    """
    distinct = sorted(set(prices))
    if len(distinct) < len(PRICE_BANDS):
        return []
    return statistics.quantiles(prices, n=len(PRICE_BANDS), method="inclusive")


def price_band(price: float, edges: list[float]) -> str:
    """Which band a price falls in. Bands are ordered cheapest first."""
    if not edges:
        return PRICE_BANDS[0]
    for index, edge in enumerate(edges):
        if price <= edge:
            return PRICE_BANDS[index]
    return PRICE_BANDS[-1]


def build_rows(products: list[dict], extra: dict[str, dict]) -> list[dict]:
    """
    One feature row per product.

    `products` are the eligible Phase 1 rows; `extra` is price and collections
    keyed by product gid, from catalog.fetch_product_features.
    """
    total = len(products)
    frequency = tag_document_frequency(products)
    prices = [extra.get(p["product_gid"], {}).get("price_min", 0.0) for p in products]
    edges = price_band_edges(prices)

    rows = []
    for product in products:
        more = extra.get(product["product_gid"], {})
        price = more.get("price_min", 0.0)
        rows.append(
            {
                "product_id": product["product_id"],
                "product_gid": product["product_gid"],
                "handle": product["handle"],
                "title": product["title"],
                # The colorway group. Same title means same style in another
                # colour, so widgets show one product per style_key.
                "style_key": product["title"],
                "product_type": product.get("product_type", ""),
                "product_type_normalised": normalise_product_type(
                    product.get("product_type", "")
                ),
                "price": price,
                "price_band": price_band(price, edges),
                "currency": more.get("currency", ""),
                "collections": more.get("collections", []),
                "season": season_of(product),
                "published_at": product.get("published_at"),
                "tags": split_tags(product.get("tags", "")),
                "signal_tags": signal_tags(product, frequency, total),
            }
        )
    return rows


def coverage(rows: list[dict], frequency: dict[str, int], total: int) -> dict:
    """
    Tag quality, measured rather than assumed - the Phase 2 exit criterion and
    the caveats.md section 5 audit in one.
    """
    signal_counts = [len(r["signal_tags"]) for r in rows]
    return {
        "products": len(rows),
        "styles": len({r["style_key"] for r in rows}),
        "distinct_tags": len(frequency),
        "near_universal": sorted(
            t for t, c in frequency.items() if c >= total * NEAR_UNIVERSAL_CUTOFF
        ),
        "single_product_tags": sum(1 for c in frequency.values() if c < MIN_TAG_PRODUCTS),
        "signal_tags": sum(
            1 for t, c in frequency.items() if is_signal_tag(t, c, total)
        ),
        "signal_tags_per_product_min": min(signal_counts) if signal_counts else 0,
        "signal_tags_per_product_avg": (
            round(sum(signal_counts) / len(signal_counts), 1) if signal_counts else 0
        ),
        "products_with_no_signal_tags": sum(1 for c in signal_counts if c == 0),
        "products_with_no_season": sum(1 for r in rows if not r["season"]),
        "products_with_no_collections": sum(1 for r in rows if not r["collections"]),
    }


def check(rows: list[dict]) -> list[str]:
    """Self-check, same stance as verify.py: assert the result, not the code."""
    problems = []

    no_style = [r for r in rows if not r["style_key"]]
    if no_style:
        problems.append(f"{len(no_style)} row(s) have no style_key")

    no_type = [r for r in rows if not r["product_type_normalised"]]
    if no_type:
        problems.append(
            f"{len(no_type)} row(s) have no normalised product type, "
            f"e.g. {no_type[0]['title']!r}"
        )

    bad_band = [r for r in rows if r["price_band"] not in PRICE_BANDS]
    if bad_band:
        problems.append(f"{len(bad_band)} row(s) landed outside every price band")

    free = [r for r in rows if r["price"] <= 0]
    if free:
        problems.append(
            f"{len(free)} row(s) have no price, e.g. {free[0]['title']!r}"
        )

    ids = [r["product_id"] for r in rows]
    if len(ids) != len(set(ids)):
        problems.append(f"{len(ids) - len(set(ids))} duplicate product_id(s)")

    return problems
