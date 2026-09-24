"""
Attribution - what an order is counted as having earned.

Two numbers per order, and the difference between them is the whole point:
`total` is the entire order, `direct_total` only the product the shopper was
actually recommended. The second is what stops a click on a recommendation
from claiming credit for a sweater the shopper found on their own.
"""

from scripts.attribute_orders import block_of, direct_total, product_of


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
    assert product_of(o) == "cheers-witches"


def test_no_ymal_attributes_at_all():
    o = order(attributes=[{"key": "gift-wrap", "value": "yes"}])
    assert block_of(o) is None
    assert product_of(o) is None
    assert direct_total(o, None) == 0


def test_counts_only_the_recommended_product():
    # The shopper clicked one sweater and bought two things.
    o = order(lines=[line("cheers-witches", 148), line("santa-hat", 149)])
    assert direct_total(o, "cheers-witches") == 148


def test_zero_when_they_bought_something_else():
    # The order still counts as ASSISTED - it just earned YMAL nothing direct.
    o = order(lines=[line("santa-hat", 149)])
    assert direct_total(o, "cheers-witches") == 0


def test_two_of_the_same_product_is_one_line():
    # Quantity is already in the line's discounted total.
    o = order(lines=[line("cheers-witches", 296)])
    assert direct_total(o, "cheers-witches") == 296


def test_a_line_added_from_the_checkout_block_counts_itself():
    # Checkout adds straight to the order, so there is no click and no product
    # on the cart - the line carries the marker instead.
    o = order(lines=[
        line("santa-hat", 149),
        line("cheers-witches", 148, [{"key": "YMAL block", "value": "recently_viewed_checkout"}]),
    ])
    assert direct_total(o, None) == 148


def test_discounted_price_not_list_price():
    o = order(lines=[line("cheers-witches", 74.5)])
    assert direct_total(o, "cheers-witches") == 74.5
