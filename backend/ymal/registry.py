"""
The block and page-template registry — docs/config-contract.md sections 4 and 5.

This is the server's copy. frontend/src/lib/blocks.js and lib/pageTemplates.js
hold a second one, kept deliberately as a static fallback so an API outage
degrades the console to "not connected" rather than a blank screen. When the
two disagree, this file is right.

Adding a block means editing both, plus adding it to ymal/blocks/ — a block
configured here with nothing computing it produces a page that renders nothing.

The descriptions that quote a window are built from settings rather than
written out, because they are what the console shows the web team. Top
Selling said "the last 90 days" for a day after the window became 14, which
is worse than no description at all - it is a wrong one, in the one place
someone would go to check.
"""

from ymal import settings

# At most four blocks on one page. A page of nothing but recommendations sells
# nothing.
MAX_BLOCKS_PER_TEMPLATE = 4

BLOCKS = [
    {
        "id": "featured",
        "label": "Featured Products",
        "description": "Products sharing tags with the one being viewed.",
        "requires_anchor": True,
        "default_heading": "You May Also Like",
        "default_slots": 6,
    },
    {
        "id": "trending",
        "label": "Trending Products",
        "description": (
            f"Rising: selling more in the last {settings.TRENDING_WINDOW_DAYS} "
            f"days than the {settings.TRENDING_WINDOW_DAYS} before."
        ),
        "requires_anchor": False,
        "default_heading": "Trending Now",
        "default_slots": 6,
    },
    {
        "id": "top_selling",
        "label": "Top Selling",
        "description": (
            f"Plain volume over the last {settings.TOP_SELLING_WINDOW_DAYS} days."
        ),
        "requires_anchor": False,
        "default_heading": "Top Selling",
        "default_slots": 6,
    },
    {
        "id": "new_arrivals",
        "label": "New Arrivals",
        "description": (
            f"Published in the last {settings.NEW_ARRIVALS_WINDOW_DAYS} days, "
            "newest first."
        ),
        "requires_anchor": False,
        "default_heading": "New Arrivals",
        "default_slots": 6,
    },
    {
        "id": "recently_viewed",
        "label": "Recently Viewed",
        "description": "The shopper's own history. Lives in their browser, not on our server.",
        "requires_anchor": False,
        "default_heading": "Recently Viewed",
        "default_slots": 4,
    },
]

# `anchor` marks a template that has a product to be "about". Only `product`
# does in v1: cart and thank_you could derive one from their contents, but
# "which of four items is the anchor" is a design decision with its own rules,
# deliberately left out (config-contract.md section 4).
#
# `live` marks the two that ship first. The list is complete from the start so
# that widening later is configuration rather than a schema migration.
PAGE_TEMPLATES = [
    {"id": "product", "label": "Product Page", "live": True, "anchor": True},
    {"id": "home", "label": "Home Page", "live": True, "anchor": False},
    {"id": "cart", "label": "Cart Page", "live": False, "anchor": False},
    {"id": "collection", "label": "Collection Pages", "live": False, "anchor": False},
    {"id": "search", "label": "Search Results", "live": False, "anchor": False},
    {"id": "not_found", "label": "404 Not Found", "live": False, "anchor": False},
    {"id": "blog", "label": "Blog Posts", "live": False, "anchor": False},
    {"id": "account", "label": "Account / Login", "live": False, "anchor": False},
    {"id": "thank_you", "label": "Thank-you Page", "live": False, "anchor": False},
]


def block_ids() -> set[str]:
    return {b["id"] for b in BLOCKS}


def page_template_ids() -> set[str]:
    return {t["id"] for t in PAGE_TEMPLATES}


def block_by_id(block_id: str) -> dict | None:
    return next((b for b in BLOCKS if b["id"] == block_id), None)


def template_by_id(template_id: str) -> dict | None:
    return next((t for t in PAGE_TEMPLATES if t["id"] == template_id), None)


def block_allowed_on(block_id: str, template_id: str) -> bool:
    """
    Whether this block may be placed on this page template.

    A block needing an anchor can only go where a product exists to anchor it.
    Unknown ids are not allowed — the caller validates them separately and gets
    a better error, but this must never answer True for something it does not
    recognise.
    """
    block = block_by_id(block_id)
    template = template_by_id(template_id)
    if block is None or template is None:
        return False
    return not block["requires_anchor"] or template["anchor"]


def supported_page_templates(block_id: str) -> list[str]:
    """Every template this block may be placed on, in registry order."""
    return [
        t["id"] for t in PAGE_TEMPLATES if block_allowed_on(block_id, t["id"])
    ]
