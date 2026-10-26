"""
Attribution - what an order is counted as having earned.

Two numbers per order, and the difference between them is the whole point:
`total` is the entire order, `direct_total` only the product the shopper was
actually recommended. The second is what stops a click on a recommendation
from claiming credit for a sweater the shopper found on their own.
"""

from scripts.attribute_orders import block_of, direct_total, products_of


def order(*, attributes=None, lines=()):
    return {
        "customAttributes": attributes or [],
        "lineItems": {"nodes": list(lines)},
    }


def line(handle, amount, attributes=None):
    return {
        "product": {"handle": handle},
        "customAttributes": attributes or [],
        "discountedTotalSet": {"shopMoney": {"amount": str(amount)}},
    }


def test_reads_the_block_and_product_off_the_order():
    o = order(attributes=[
        {"key": "YMAL block", "value": "featured"},
        {"key": "YMAL product", "value": "cheers-witches"},
    ])
    assert block_of(o) == "featured"
    assert products_of(o) == ["cheers-witches"]


def test_no_ymal_attributes_at_all():
    o = order(attributes=[{"key": "gift-wrap", "value": "yes"}])
    assert block_of(o) is None
    assert products_of(o) == []
    assert direct_total(o, []) == 0


def test_counts_only_the_recommended_product():
    # The shopper clicked one sweater and bought two things.
    o = order(lines=[line("cheers-witches", 148), line("santa-hat", 149)])
    assert direct_total(o, ["cheers-witches"]) == 148


def test_zero_when_they_bought_something_else():
    # The order still counts as ASSISTED - it just earned YMAL nothing direct.
    o = order(lines=[line("santa-hat", 149)])
    assert direct_total(o, ["cheers-witches"]) == 0


def test_two_of_the_same_product_is_one_line():
    # Quantity is already in the line's discounted total.
    o = order(lines=[line("cheers-witches", 296)])
    assert direct_total(o, ["cheers-witches"]) == 296


def test_a_line_added_from_the_checkout_block_counts_itself():
    # Checkout adds straight to the order, so there is no click and no product
    # on the cart - the line carries the marker instead.
    o = order(lines=[
        line("santa-hat", 149),
        line("cheers-witches", 148, [{"key": "YMAL block", "value": "recently_viewed_checkout"}]),
    ])
    assert direct_total(o, []) == 148


def test_discounted_price_not_list_price():
    o = order(lines=[line("cheers-witches", 74.5)])
    assert direct_total(o, ["cheers-witches"]) == 74.5


# Every recommended product the shopper clicked or added, not just the last.
# "YMAL product" is overwritten on each click; "YMAL products" keeps the list.

def test_reads_every_clicked_product():
    o = order(attributes=[
        {"key": "YMAL block", "value": "cart_popup"},
        {"key": "YMAL product", "value": "key-west"},
        {"key": "YMAL products", "value": "eryn-cardigan,rihanna-cardi,key-west"},
    ])
    assert products_of(o) == ["eryn-cardigan", "rihanna-cardi", "key-west"]


def test_counts_every_clicked_product_that_was_bought():
    # Three sweaters, each from a YMAL block: all three are direct.
    o = order(
        attributes=[
            {"key": "YMAL product", "value": "key-west"},
            {"key": "YMAL products", "value": "eryn-cardigan,rihanna-cardi,key-west"},
        ],
        lines=[
            line("eryn-cardigan", 148),
            line("rihanna-cardi", 152),
            line("key-west", 148),
            line("santa-hat", 149),
        ],
    )
    assert direct_total(o, products_of(o)) == 448


def test_a_clicked_product_not_bought_adds_nothing():
    o = order(
        attributes=[{"key": "YMAL products", "value": "eryn-cardigan,rihanna-cardi"}],
        lines=[line("eryn-cardigan", 148), line("santa-hat", 149)],
    )
    assert direct_total(o, products_of(o)) == 148


def test_the_last_product_counts_even_if_the_list_was_reverted():
    # Another app can write the cart from a stale copy and put an older list
    # back. The single last product is still a click, so it is kept too.
    o = order(attributes=[
        {"key": "YMAL product", "value": "key-west"},
        {"key": "YMAL products", "value": "eryn-cardigan"},
    ])
    assert products_of(o) == ["eryn-cardigan", "key-west"]


def test_an_order_from_before_the_list_still_has_its_one_product():
    o = order(attributes=[{"key": "YMAL product", "value": "cheers-witches"}])
    assert products_of(o) == ["cheers-witches"]


def test_blanks_and_repeats_in_the_list_are_ignored():
    o = order(attributes=[{"key": "YMAL products", "value": " eryn-cardigan, ,eryn-cardigan,key-west "}])
    assert products_of(o) == ["eryn-cardigan", "key-west"]
