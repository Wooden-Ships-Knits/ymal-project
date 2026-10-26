"""
Products a shopper personalizes - a name or number knitted in - before buying.

Textify collects that input on the product page, and only there. A YMAL card
that adds straight to the cart skips it, and the order arrives with no name and
no number. So the theme reads this list and, for these products, swaps the
card's quick add for a link to the product page.

Matched by TITLE, not by id, because that is how Textify itself decides which
products carry a field ("Product title | Equals"), and one title covers every
colorway: CUSTOMIZABLE NUMBER JERSEY LIGHTWEIGHT is a dozen products. Stored
upper-cased and the theme compares upper-cased, so case never decides it.

Kept in the ymal.config document beside tuning, so it inherits the validator,
the previous-version copy and undo.
"""

import csv

from ymal import settings

CONFIG_KEY = "personalized"

ACTIVE_PRODUCTS = settings.PHASE1_DIR / "active_products.csv"


def clean(titles: list) -> list:
    """
    Trim, upper-case, and drop blanks and repeats, keeping the order given.

    Only strings are cleaned. Anything else is passed through untouched, so the
    validator reports it rather than this quietly dropping it.
    """
    seen: set[str] = set()
    cleaned = []
    for title in titles:
        if not isinstance(title, str):
            cleaned.append(title)
            continue
        title = " ".join(title.split()).upper()
        if title and title not in seen:
            seen.add(title)
            cleaned.append(title)
    return cleaned


def known_titles() -> list[str]:
    """
    Every distinct active product title, for the console's picker.

    Suggestions only: a title missing from here (a product not yet fetched, or
    one the nightly run excludes) can still be typed in.
    """
    try:
        with open(ACTIVE_PRODUCTS, newline="") as f:
            titles = {row["title"].strip().upper() for row in csv.DictReader(f)}
    except FileNotFoundError:
        return []
    return sorted(t for t in titles if t)
