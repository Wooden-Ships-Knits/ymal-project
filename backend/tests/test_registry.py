"""
The registry mirrors frontend/src/lib/blocks.js and lib/pageTemplates.js.
Two copies exist on purpose (spec section 7) — these tests pin the server's,
which is authoritative.
"""

from ymal import registry


def test_five_blocks():
    assert registry.block_ids() == {
        "featured",
        "trending",
        "top_selling",
        "new_arrivals",
        "recently_viewed",
    }


def test_nine_page_templates():
    assert registry.page_template_ids() == {
        "product",
        "home",
        "cart",
        "collection",
        "search",
        "not_found",
        "blog",
        "account",
        "thank_you",
    }


def test_only_product_carries_an_anchor_in_v1():
    anchored = {t["id"] for t in registry.PAGE_TEMPLATES if t["anchor"]}
    assert anchored == {"product"}


def test_featured_requires_an_anchor_so_only_product_accepts_it():
    assert registry.block_allowed_on("featured", "product") is True
    assert registry.block_allowed_on("featured", "home") is False
    assert registry.block_allowed_on("featured", "cart") is False


def test_anchorless_blocks_go_anywhere():
    for template_id in registry.page_template_ids():
        assert registry.block_allowed_on("trending", template_id) is True


def test_unknown_ids_are_not_allowed():
    assert registry.block_allowed_on("nonsense", "product") is False
    assert registry.block_allowed_on("trending", "nonsense") is False


def test_supported_page_templates_for_featured_is_product_only():
    assert registry.supported_page_templates("featured") == ["product"]


def test_product_and_home_are_the_v1_templates():
    live = {t["id"] for t in registry.PAGE_TEMPLATES if t["live"]}
    assert live == {"product", "home"}


def test_default_slots_match_the_contract():
    assert registry.block_by_id("featured")["default_slots"] == 6
    assert registry.block_by_id("recently_viewed")["default_slots"] == 4
