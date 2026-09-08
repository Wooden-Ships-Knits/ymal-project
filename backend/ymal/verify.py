"""
Self-check on the eligible list.

The rule is applied in one place and checked here in another, deliberately: if
eligibility.py has a bug, re-running eligibility.py to check it would agree
with itself. These assertions are written from the rule as stated in words, not
from the code that implements it.

Runs on every fetch, so a broken rule surfaces the day it breaks rather than
months later when someone notices the widget looks wrong.

Pure functions, no I/O.
"""

from ymal import settings


def check(rows: list[dict]) -> list[str]:
    """Every violated invariant, as readable lines. Empty means all passed."""
    return [
        problem
        for problem in (
            _no_eligible_is_on_sale(rows),
            _every_eligible_is_at_bali(rows),
            _no_eligible_is_unpublished(rows),
            _reasons_add_up(rows),
        )
        if problem
    ]


def _eligible(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["eligible"]]


def _no_eligible_is_on_sale(rows: list[dict]) -> str | None:
    marker = settings.SALE_MARKER.lower()
    bad = [r for r in _eligible(rows) if marker in (r["title"] or "").lower()]
    if bad:
        return (
            f"{len(bad)} eligible product(s) carry {settings.SALE_MARKER} in the "
            f"title, e.g. {bad[0]['title']!r}"
        )
    return None


def _every_eligible_is_at_bali(rows: list[dict]) -> str | None:
    bad = [r for r in _eligible(rows) if not r.get("at_bali")]
    if bad:
        return (
            f"{len(bad)} eligible product(s) are not stocked at Bali, "
            f"e.g. {bad[0]['title']!r}"
        )
    return None


def _no_eligible_is_unpublished(rows: list[dict]) -> str | None:
    if not settings.EXCLUDE_UNPUBLISHED:
        return None
    bad = [r for r in _eligible(rows) if not r.get("published")]
    if bad:
        return (
            f"{len(bad)} eligible product(s) have no online-store URL, "
            f"e.g. {bad[0]['title']!r}"
        )
    return None


def _reasons_add_up(rows: list[dict]) -> str | None:
    """Every ineligible product must say why, and no eligible one may."""
    silent = [r for r in rows if not r["eligible"] and not r.get("reason_if_not")]
    if silent:
        return f"{len(silent)} ineligible product(s) give no reason"

    explained = [r for r in _eligible(rows) if r.get("reason_if_not")]
    if explained:
        return f"{len(explained)} eligible product(s) carry an exclusion reason"

    return None
