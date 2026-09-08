"""
The Phase 2 feature table. Pure derivation, so all of it runs offline.

Content similarity is built on these values - a wrong feature is invisible
until a customer sees a bad recommendation.
"""

from ymal import features


def product(**kw):
    base = {
        "product_id": "1",
        "product_gid": "gid://shopify/Product/1",
        "handle": "charlotte-crew",
        "title": "CHARLOTTE CREW COTTON",
        "product_type": "Crewneck",
        "published_at": "2026-09-01T00:00:00Z",
        "tags": "casual, autumn, Crew, cotton-vo",
    }
    base.update(kw)
    return base


def test_tags_split_from_shopifys_comma_string():
    assert features.split_tags("a, b ,c") == ["a", "b", "c"]
    assert features.split_tags("") == []
    assert features.split_tags(None) == []


def test_the_three_vneck_spellings_collapse():
    # 42 products split across three types otherwise, diluting any "same type"
    # signal by two thirds.
    assert (
        features.normalise_product_type("V-Neck")
        == features.normalise_product_type("V-neck")
        == features.normalise_product_type("Vneck")
        == "vneck"
    )


def test_fall_and_autumn_are_the_same_season():
    assert features.season_of(product(tags="fall")) == "autumn"
    assert features.season_of(product(tags="autumn")) == "autumn"


def test_no_season_tag_gives_none():
    assert features.season_of(product(tags="casual, Crew")) is None


def test_a_tag_on_every_product_is_not_a_signal():
    assert features.is_signal_tag("casual", 100, 100) is False


def test_a_filter_app_tag_is_never_a_signal():
    # Describes available sizes, not the garment, and every product has them.
    assert features.is_signal_tag("FILTERBY-S/M", 5, 100) is False


def test_a_tag_on_one_product_only_is_not_a_signal():
    assert features.is_signal_tag("unique-thing", 1, 100) is False


def test_a_mid_frequency_tag_is_a_signal():
    assert features.is_signal_tag("cotton-vo", 40, 100) is True


def test_signal_tags_keep_only_what_can_distinguish():
    # 10 products: "casual" on all of them, "rare" on one, "cotton" on half.
    # Only "cotton" can tell one product from another.
    products = [product(product_id="1", tags="casual, rare, cotton")]
    products += [
        product(product_id=str(i), tags="casual, cotton") for i in range(2, 6)
    ]
    products += [product(product_id=str(i), tags="casual") for i in range(6, 11)]
    frequency = features.tag_document_frequency(products)

    tags = features.signal_tags(products[0], frequency, len(products))

    assert tags == ["cotton"]


def test_price_bands_need_enough_distinct_prices():
    assert features.price_band_edges([10.0, 10.0, 10.0]) == []
    # Everything lands in one band rather than inventing boundaries.
    assert features.price_band(10.0, []) == "budget"


def test_price_bands_order_cheapest_first():
    edges = features.price_band_edges([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])

    assert features.price_band(10.0, edges) == "budget"
    assert features.price_band(1000.0, edges) == "luxury"


def test_style_key_groups_colorways():
    rows = features.build_rows(
        [product(product_id="1", handle="a"), product(product_id="2", handle="b")],
        {},
    )
    assert rows[0]["style_key"] == rows[1]["style_key"]


def test_a_clean_table_passes_the_self_check():
    rows = features.build_rows([product()], {"gid://shopify/Product/1": {"price_min": 144.0}})
    assert features.check(rows) == []


def test_a_missing_price_is_caught():
    rows = features.build_rows([product()], {})
    assert any("no price" in p for p in features.check(rows))


def test_a_missing_product_type_is_caught():
    rows = features.build_rows(
        [product(product_type="")], {"gid://shopify/Product/1": {"price_min": 1.0}}
    )
    assert any("normalised product type" in p for p in features.check(rows))


def test_duplicate_ids_are_caught():
    rows = features.build_rows(
        [product(), product()], {"gid://shopify/Product/1": {"price_min": 1.0}}
    )
    assert any("duplicate" in p for p in features.check(rows))
