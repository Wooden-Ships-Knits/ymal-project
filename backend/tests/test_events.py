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
