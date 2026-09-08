"""
The Sheet diff - caveats.md section 0, the Phase 1 answer key.

Sheets mangle product ids in predictable ways, so the id normalising is worth
as much coverage as the comparison itself: a diff that silently matches nothing
because of a trailing ".0" would read as "the rule is completely wrong".
"""

from ymal import sheet_diff


PRODUCTS = [
    {"product_id": "1", "title": "CHARLOTTE CREW", "eligible": True, "reason_if_not": ""},
    {"product_id": "2", "title": "BEACH V *SALE*", "eligible": False, "reason_if_not": "sale_marker"},
    {"product_id": "3", "title": "RIHANNA CARDI", "eligible": True, "reason_if_not": ""},
    {"product_id": "4", "title": "FIXED THING", "eligible": False, "reason_if_not": "fixed_stock"},
]


def test_a_plain_id_is_unchanged():
    assert sheet_diff.normalise_id("7537242669104") == "7537242669104"


def test_a_gid_url_reduces_to_the_bare_id():
    assert sheet_diff.normalise_id("gid://shopify/Product/7537242669104") == "7537242669104"


def test_a_float_from_a_numeric_column_loses_its_decimal():
    # Sheets stores a long id as a number and exports it as "7537242669104.0".
    assert sheet_diff.normalise_id("7537242669104.0") == "7537242669104"


def test_whitespace_and_blanks():
    assert sheet_diff.normalise_id("  123  ") == "123"
    assert sheet_diff.normalise_id("") == ""
    assert sheet_diff.normalise_id(None) == ""


def test_headings_match_regardless_of_spacing_and_case():
    headings = ["Product ID", "Title"]
    assert sheet_diff.find_column(headings, sheet_diff.ID_HEADINGS) == "Product ID"

    assert sheet_diff.find_column(["product_id"], sheet_diff.ID_HEADINGS) == "product_id"
    assert sheet_diff.find_column(["Nope"], sheet_diff.ID_HEADINGS) is None


def test_identical_lists_report_match():
    result = sheet_diff.compare(PRODUCTS, {"1", "3"})

    assert result["verdict"] == "match"
    assert result["agreed"] == 2
    assert result["missing_from_api"] == []
    assert result["extra_in_api"] == []


def test_api_larger_means_the_rule_is_too_permissive():
    result = sheet_diff.compare(PRODUCTS, {"1"})

    assert result["verdict"] == "api_larger"
    assert [p["product_id"] for p in result["extra_in_api"]] == ["3"]


def test_api_smaller_means_the_rule_is_too_strict():
    result = sheet_diff.compare(PRODUCTS, {"1", "2", "3", "4"})

    assert result["verdict"] == "api_smaller"
    assert {p["product_id"] for p in result["missing_from_api"]} == {"2", "4"}


def test_same_size_but_different_rows_is_not_a_match():
    # Two errors cancelling out. The count alone would look fine.
    result = sheet_diff.compare(PRODUCTS, {"1", "4"})

    assert result["verdict"] == "same_size_different_rows"
    assert [p["product_id"] for p in result["missing_from_api"]] == ["4"]
    assert [p["product_id"] for p in result["extra_in_api"]] == ["3"]


def test_ids_not_in_the_catalog_are_separated_from_rule_disagreements():
    result = sheet_diff.compare(PRODUCTS, {"1", "3", "999"})

    assert result["not_in_catalog"] == ["999"]
    assert result["missing_from_api"] == []


def test_reasons_are_grouped_largest_first():
    grouped = sheet_diff.group_by_reason(
        [
            {"reason_if_not": "fixed_stock"},
            {"reason_if_not": "sale_marker"},
            {"reason_if_not": "fixed_stock"},
        ]
    )

    assert list(grouped) == ["fixed_stock", "sale_marker"]
    assert len(grouped["fixed_stock"]) == 2


def test_sheet_ids_are_normalised_on_read():
    rows = [{"Product ID": "gid://shopify/Product/1"}, {"Product ID": "3.0"}, {"Product ID": ""}]

    assert sheet_diff.read_sheet_ids(rows, "Product ID") == {"1", "3"}
