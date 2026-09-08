"""
Diff the API's eligible list against the hand-built Google Sheet.

caveats.md section 0: the Sheet is the answer key. Derive eligibility from the
API, diff against the Sheet, and read the result:

    lists match          rule validated
    API list larger      rule too permissive - something ineligible is leaking
    API list smaller     rule too strict - likely a location or marker miss
    rows disagree        each mismatch names a specific broken assumption

Pure functions, no I/O, so the comparison can be tested without a real export.
The Sheet is a snapshot and validates the rule; it must never become the source
of truth (memory.md decisions 7 and 9).
"""

# Column headings a hand-built sheet plausibly uses for the product id. Matched
# case-insensitively, after stripping spaces and underscores, because nobody
# hand-types a header consistently.
ID_HEADINGS = ("productid", "id", "shopifyid", "productgid", "gid")
HANDLE_HEADINGS = ("handle", "producthandle", "slug", "url")


def normalise_heading(heading: str) -> str:
    return "".join(ch for ch in (heading or "").lower() if ch.isalnum())


def normalise_id(value: object) -> str:
    """
    Reduce any way of writing a product id to one comparable string.

    Sheets mangle ids in predictable ways: a gid URL pasted whole, a float from
    a numeric column ("7537242669104.0"), stray whitespace. All of these mean
    the same product.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if "/" in text:  # gid://shopify/Product/7537242669104
        text = text.rstrip("/").rsplit("/", 1)[-1]
    if text.endswith(".0"):
        text = text[:-2]
    return text


def find_column(headings: list[str], candidates: tuple[str, ...]) -> str | None:
    """The first heading matching any candidate, or None."""
    normalised = {normalise_heading(h): h for h in headings}
    for candidate in candidates:
        if candidate in normalised:
            return normalised[candidate]
    return None


def read_sheet_ids(rows: list[dict], id_column: str) -> set[str]:
    """Every non-empty, normalised product id in the sheet."""
    return {
        normalise_id(row.get(id_column))
        for row in rows
        if normalise_id(row.get(id_column))
    }


def compare(products: list[dict], sheet_ids: set[str]) -> dict:
    """
    Compare the API's verdict against the sheet's.

    The sheet lists products believed eligible, so:

      missing_from_api   in the sheet, the API says ineligible -> too strict,
                         or the sheet is wrong. reason_if_not says which.
      extra_in_api       the API says eligible, the sheet does not list it ->
                         too permissive, something is leaking through.
      not_in_catalog     in the sheet, not in the API's active list at all.
                         Not a rule disagreement - the product went inactive,
                         was deleted, or the id is wrong.
    """
    by_id = {normalise_id(p["product_id"]): p for p in products}
    api_eligible = {pid for pid, p in by_id.items() if p["eligible"]}

    missing_from_api = []
    not_in_catalog = []

    for pid in sorted(sheet_ids):
        product = by_id.get(pid)
        if product is None:
            not_in_catalog.append(pid)
        elif not product["eligible"]:
            missing_from_api.append(product)

    extra_in_api = [by_id[pid] for pid in sorted(api_eligible - sheet_ids)]

    return {
        "sheet_count": len(sheet_ids),
        "api_eligible_count": len(api_eligible),
        "agreed": len(api_eligible & sheet_ids),
        "missing_from_api": missing_from_api,
        "extra_in_api": extra_in_api,
        "not_in_catalog": not_in_catalog,
        "verdict": verdict(len(api_eligible), len(sheet_ids), api_eligible, sheet_ids),
    }


def verdict(api_count: int, sheet_count: int, api_set: set, sheet_set: set) -> str:
    """The four outcomes from caveats.md section 0."""
    if api_set == sheet_set:
        return "match"
    if api_count > sheet_count:
        return "api_larger"
    if api_count < sheet_count:
        return "api_smaller"
    return "same_size_different_rows"


def group_by_reason(products: list[dict]) -> dict[str, list[dict]]:
    """
    Bucket disagreements by why the API excluded them.

    This is the diagnostic: if every miss is fixed_stock the location pattern
    is wrong, if every miss is sale_marker the marker is wrong. A spread across
    reasons means the sheet and the rule disagree about the rule itself.
    """
    grouped: dict[str, list[dict]] = {}
    for product in products:
        grouped.setdefault(product.get("reason_if_not") or "unknown", []).append(product)
    return dict(sorted(grouped.items(), key=lambda kv: -len(kv[1])))
