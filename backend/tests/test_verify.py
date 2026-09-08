"""
The self-check. Written from the rule as stated in words, so a bug in
eligibility.py cannot pass by agreeing with itself.
"""

from ymal import verify


def row(**kw):
    base = {
        "title": "CHARLOTTE CREW",
        "eligible": True,
        "at_bali": True,
        "published": True,
        "reason_if_not": "",
    }
    base.update(kw)
    return base


def test_a_clean_list_passes():
    assert verify.check([row(), row(title="RIHANNA CARDI")]) == []


def test_an_ineligible_row_with_a_reason_passes():
    rows = [row(), row(eligible=False, at_bali=False, reason_if_not="fixed_stock")]
    assert verify.check(rows) == []


def test_a_sale_product_marked_eligible_is_caught():
    problems = verify.check([row(title="BEACH V *SALE*")])
    assert len(problems) == 1
    assert "*SALE*" in problems[0]


def test_a_non_bali_product_marked_eligible_is_caught():
    problems = verify.check([row(at_bali=False)])
    assert any("not stocked at Bali" in p for p in problems)


def test_an_unpublished_product_marked_eligible_is_caught():
    problems = verify.check([row(published=False)])
    assert any("no online-store URL" in p for p in problems)


def test_an_ineligible_product_with_no_reason_is_caught():
    problems = verify.check([row(eligible=False, reason_if_not="")])
    assert any("no reason" in p for p in problems)


def test_an_eligible_product_carrying_a_reason_is_caught():
    problems = verify.check([row(reason_if_not="fixed_stock")])
    assert any("carry an exclusion reason" in p for p in problems)


def test_several_problems_are_all_reported():
    problems = verify.check([row(title="X *SALE*", at_bali=False, published=False)])
    assert len(problems) == 3
