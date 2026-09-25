"""
Storefront tracking events.

POST /api/events is the only unauthenticated write in the project, so the
validation is the security boundary and gets tested as one.
"""

import pytest

from ymal import db, events


def event(**kw):
    base = {
        "type": "click",
        "block": "trending",
        "page_type": "home",
        "session": "abc123",
        "handle": "charlotte-crew",
        "position": 3,
    }
    base.update(kw)
    return base


def test_a_well_formed_event_passes():
    assert events.validate(event()) == []


@pytest.mark.parametrize("field,value", [
    ("type", "purchase"),
    ("block", "bestsellers"),
    ("page_type", "checkout"),
])
def test_values_outside_the_known_sets_are_rejected(field, value):
    assert events.validate(event(**{field: value}))


def test_an_impression_may_omit_the_handle():
    # An impression is about the row, not one product in it.
    assert events.validate(event(type="impression", handle=None)) == []


def test_a_click_without_a_handle_is_rejected():
    assert events.validate(event(handle=None))


def test_an_oversized_session_is_rejected():
    assert events.validate(event(session="x" * 65))


def test_a_boolean_position_is_rejected():
    # bool is a subclass of int in Python, so True would otherwise be rank 1.
    assert events.validate(event(position=True))


def test_a_position_outside_the_range_is_rejected():
    assert events.validate(event(position=0))
    assert events.validate(event(position=101))


def test_unknown_fields_are_dropped_not_stored():
    # An endpoint that keeps whatever it is sent is how personal data arrives
    # by accident.
    row = events.normalise(event(email="someone@example.com", ip="1.2.3.4"))

    assert set(row) == {
        "type", "block", "page_type", "session", "handle", "anchor", "position"
    }


def test_a_batch_keeps_the_good_events_and_reports_the_rest():
    # The browser sends by beacon and cannot retry, so one malformed event must
    # not lose the others alongside it.
    good, problems = events.clean_batch([event(), event(block="nope"), event()])

    assert len(good) == 2
    assert len(problems) == 1
    assert problems[0].startswith("[1]")


def test_an_oversized_batch_is_rejected_whole():
    good, problems = events.clean_batch([event()] * (events.MAX_BATCH + 1))

    assert good == []
    assert "at most" in problems[0]


def test_a_batch_that_is_not_a_list_is_rejected():
    good, problems = events.clean_batch({"type": "click"})

    assert good == []
    assert problems == ["events must be a list"]


def test_no_database_configured_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    with pytest.raises(db.NoDatabase):
        db.url()


def test_an_awkward_password_does_not_break_the_connection_string(monkeypatch):
    # A "/" in a password terminates a URL's authority section, which made the
    # host parse as the database name - an error that reads as DNS failure.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD", "aw/kward:pass@word")

    conninfo = db.url()

    assert "host=db" in conninfo
    assert "dbname=ymal" in conninfo


class TestPageTypesTheThemeCanActuallySend:
    """
    page_type is derived from Shopify's template name, and an unlisted value is
    REJECTED - silently, from the shopper's point of view. So the allowlist has
    to cover everything the theme can produce, or a block placed on the wrong
    kind of page records nothing and looks exactly like a block nobody scrolled
    to.
    """

    def base(self, **over):
        event = {
            "type": "click",
            "block": "featured",
            "page_type": "product",
            "session": "abc",
            "handle": "some-product",
        }
        event.update(over)
        return event

    def test_accepts_a_regular_shopify_page(self):
        """template.name is `page` for any Shopify page. A block can go there."""
        assert events.validate(self.base(page_type="page")) == []

    def test_accepts_unknown(self):
        """
        The theme maps any template it does not recognise to `unknown`. Storing
        that is better than dropping the event: the click still happened, and a
        bucket named unknown is a visible prompt to widen the mapping.
        """
        assert events.validate(self.base(page_type="unknown")) == []

    def test_still_rejects_something_arbitrary(self):
        """The allowlist has to stay an allowlist."""
        problems = events.validate(self.base(page_type="../../etc/passwd"))
        assert problems == ["page_type is not a known page template"]

    def test_every_page_template_in_the_registry_is_accepted(self):
        """
        The registry and this list describe the same thing from two sides. A
        template the console can place a block on must be one the API accepts.
        """
        from ymal import registry

        for template_id in registry.page_template_ids():
            assert events.validate(self.base(page_type=template_id)) == [], template_id


class TestAddToCart:
    def test_accepted_with_a_handle(self):
        assert events.validate({
            "type": "add_to_cart",
            "block": "featured",
            "page_type": "product",
            "session": "abc",
            "handle": "pumpkin-truck-crew-chunky",
        }) == []

    def test_needs_a_handle(self):
        """
        Unlike an impression, which carries a whole row, an add is about one
        product. Without the handle there is nothing to report.
        """
        problems = events.validate({
            "type": "add_to_cart",
            "block": "featured",
            "page_type": "product",
            "session": "abc",
        })
        assert "handle is required for this event type" in problems

    def test_a_null_position_is_fine(self):
        """
        The add happens on the product page, where the row that caused it is no
        longer on screen, so there is no position to report.
        """
        assert events.validate({
            "type": "add_to_cart",
            "block": "featured",
            "page_type": "product",
            "session": "abc",
            "handle": "x",
            "position": None,
            "anchor": None,
        }) == []


def test_inspired_by_views_is_an_accepted_block():
    """
    The allowlist rejects unknown blocks silently from the shopper's side, so a
    block missing from it records nothing and looks like a block nobody saw.
    """
    assert events.validate(event(block="inspired_by_views", page_type="product")) == []


def test_an_ab_label_is_a_known_block():
    # The same block placed twice, to compare positions. Both read the same
    # published list; only the name they report differs.
    assert events.known_block("top_selling_a")
    assert events.known_block("top_selling_b")
    assert events.known_block("featured_a")


def test_an_ab_label_on_an_unknown_block_is_still_unknown():
    assert not events.known_block("wiser_upsell_a")
    assert not events.known_block("_a")
    assert not events.known_block(None)


def test_only_a_and_b_are_labels():
    # Not a general "anything with a suffix" rule: c, 1, -test would all be
    # silent typos that record events nobody ever finds.
    assert not events.known_block("top_selling_c")
    assert not events.known_block("top_selling_1")
