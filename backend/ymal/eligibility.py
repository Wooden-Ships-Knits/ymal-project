"""
The eligibility rule — docs/logic.md §4.1.

A product may appear in YMAL only if BOTH hold:
    1. it is stocked at the Bali production location  -> replenishable
    2. its title does NOT contain the *SALE* marker   -> not markdown

Pure functions, no I/O. Kept separate from the fetching code so the rule can be
tested against known inputs without touching Shopify — this is the piece the
whole project hinges on, so it should be the easiest piece to verify.
"""

from ymal import settings

# Reasons a product can be excluded. Used in output and reporting.
REASON_FIXED_STOCK = "fixed_stock"
REASON_BALI_ZERO_QTY = "bali_zero_qty"
REASON_SALE_MARKER = "sale_marker"
REASON_EXCLUDED_TYPE = "excluded_type"
REASON_NO_PRODUCT_TYPE = "no_product_type"
REASON_NOT_PUBLISHED = "not_published"


def has_sale_marker(title: str) -> bool:
    """
    True if the title carries the *SALE* marker.

    Literal substring containment, never regex — "*" is a regex metacharacter,
    so a compiled "*SALE*" pattern would match something entirely different.
    """
    if settings.SALE_MARKER_CASE_SENSITIVE:
        return settings.SALE_MARKER in title
    return settings.SALE_MARKER.lower() in title.lower()


def is_excluded_type(product_type: str) -> bool:
    """
    True if the product type is one a recommendation widget should never show.

    Normalises to lowercase alphanumerics before matching, so "Gift Card",
    "Gift Cards" and "gift-cards" all collapse to the same prefix. This shop's
    productType values are inconsistent enough (V-Neck / V-neck / Vneck) that
    an exact match would leak on the next spelling.
    """
    normalised = "".join(ch for ch in (product_type or "").lower() if ch.isalnum())
    return any(
        normalised.startswith(prefix)
        for prefix in settings.EXCLUDED_PRODUCT_TYPE_PREFIXES
    )


def matches_bali(location_name: str) -> bool:
    """True if a location name looks like the Bali production location."""
    return settings.BALI_LOCATION_PATTERN.lower() in location_name.lower()


def classify(
    title: str,
    at_bali: bool,
    bali_quantity: int = 0,
    published: bool = True,
    product_type: str = "",
) -> tuple[bool, list[str]]:
    """
    Resolve eligibility for one product.

    Returns (eligible, reasons) — `reasons` is empty when eligible, and lists
    every failing condition otherwise. Collecting all reasons rather than
    short-circuiting keeps the reporting honest: a product can fail on more
    than one count, and knowing that matters when validating the rule against
    the Sheet.
    """
    reasons: list[str] = []

    if not at_bali:
        reasons.append(REASON_FIXED_STOCK)
    elif settings.REQUIRE_BALI_QUANTITY and bali_quantity <= 0:
        reasons.append(REASON_BALI_ZERO_QTY)

    if has_sale_marker(title):
        reasons.append(REASON_SALE_MARKER)

    if settings.EXCLUDE_UNPUBLISHED and not published:
        reasons.append(REASON_NOT_PUBLISHED)

    if is_excluded_type(product_type):
        reasons.append(REASON_EXCLUDED_TYPE)
    elif settings.REQUIRE_PRODUCT_TYPE and not (product_type or "").strip():
        reasons.append(REASON_NO_PRODUCT_TYPE)

    return (not reasons), reasons
