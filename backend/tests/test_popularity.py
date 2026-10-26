"""
Sales volume as a ranking signal, counted per STYLE rather than per product.

A pool row is a style - build_pool keeps one product per style_key and shows
the best-scoring colorway. So the sales number beside it has to be the style's
sales. Counting one colorway meant a sweater selling 38 across twelve colorways
scored as though it had sold 9, and on this catalog 18 of 128 styles understate
by 2x or more.

The scale matters as much as the sum. Popularity is 0-1 against the best
seller, and the raw units table is topped by things that can never be
recommended - a product that is not even active (499 units) and an add-on
service line (119). Dividing every garment by 499 squashed the whole column
into the bottom third of its range.
"""

import pytest

from ymal import similarity


def row(product_id, style, tags=("a",), season="autumn", gid=None):
    return {
        "product_id": product_id,
        "product_gid": gid or f"gid://shopify/Product/{product_id}",
        "handle": f"h{product_id}",
        "title": style,
        "style_key": style,
        "season": season,
        "product_type_normalised": "crewneck",
        "signal_tags": list(tags),
        "collections": [],
    }


class TestStyleKey:
    def test_normalises_case_and_space(self):
        """
        build_blocks keys its map on TITLE.strip().upper(); features.json keeps
        the title as Shopify has it. They have to meet somewhere.
        """
        assert similarity.style_of({"style_key": " Key West Crew "}) == "KEY WEST CREW"

    def test_missing_style_key_is_empty_not_an_error(self):
        assert similarity.style_of({}) == ""


class TestStyleUnits:
    def test_sums_every_colorway(self):
        rows = [row("1", "KEY WEST"), row("2", "KEY WEST"), row("3", "OTHER")]
        units = {
            "gid://shopify/Product/1": 9,
            "gid://shopify/Product/2": 12,
            "gid://shopify/Product/3": 4,
        }
        totals = similarity.units_by_style(rows, units)
        assert totals["KEY WEST"] == 21
        assert totals["OTHER"] == 4

    def test_counts_a_colorway_with_no_sales_as_zero(self):
        rows = [row("1", "KEY WEST"), row("2", "KEY WEST")]
        totals = similarity.units_by_style(rows, {"gid://shopify/Product/1": 9})
        assert totals["KEY WEST"] == 9

    def test_no_units_gives_no_totals(self):
        assert similarity.units_by_style([row("1", "A")], {}) == {}


class TestPopularity:
    def test_zero_when_nothing_has_sold(self):
        assert similarity.popularity({}, "A", 0) == 0.0

    def test_one_for_the_best_selling_style(self):
        assert similarity.popularity({"A": 50}, "A", 50) == 1.0

    def test_square_rooted_so_the_extremes_do_not_own_the_scale(self):
        """
        One style sells 318 units in a fortnight while most sell single digits.
        Linear, everything else would be indistinguishable from zero.
        """
        assert similarity.popularity({"A": 25}, "A", 100) == pytest.approx(0.5)

    def test_an_unknown_style_scores_zero(self):
        assert similarity.popularity({"A": 10}, "MISSING", 10) == 0.0

    def test_negative_units_cannot_drag_a_score_below_zero(self):
        assert similarity.popularity({"A": -5}, "A", 10) == 0.0


class TestTheScaleIsSetByRecommendableStyles:
    def test_most_units_ignores_products_that_are_not_in_the_pool(self):
        """
        The denominator comes from the eligible feature table, so an archived
        product or an add-on service line cannot set the top of the scale. This
        is what had every real garment scoring 0.06-0.33.
        """
        rows = [row("1", "REAL"), row("2", "ALSO REAL")]
        units = {
            "gid://shopify/Product/1": 100,
            "gid://shopify/Product/2": 50,
            # Never appears in rows: not active, or an add-on.
            "gid://shopify/Product/999": 499,
        }
        totals = similarity.units_by_style(rows, units)
        assert max(totals.values()) == 100
        assert similarity.popularity(totals, "REAL", max(totals.values())) == 1.0


class TestInThePool:
    def _pools(self, rows, units):
        return similarity.build_pools(rows, units=units)

    def test_a_many_colorway_style_outranks_a_single_one_that_sold_less(self):
        anchor = row("0", "ANCHOR")
        rows = [
            anchor,
            row("1", "MANY"),
            row("2", "MANY"),
            row("3", "MANY"),
            row("4", "ONE"),
        ]
        units = {
            "gid://shopify/Product/1": 10,
            "gid://shopify/Product/2": 10,
            "gid://shopify/Product/3": 10,  # 30 for the style
            "gid://shopify/Product/4": 20,  # more per product, less per style
        }
        pool = self._pools(rows, units)[anchor["product_id"]]
        assert [i["title"] for i in pool][0] == "MANY"

    def test_the_pool_still_shows_one_product_per_style(self):
        anchor = row("0", "ANCHOR")
        rows = [anchor, row("1", "MANY"), row("2", "MANY")]
        pool = self._pools(rows, {"gid://shopify/Product/1": 5})[anchor["product_id"]]
        assert [i["title"] for i in pool].count("MANY") == 1

    def test_popularity_reported_is_the_styles_not_the_colorways(self):
        anchor = row("0", "ANCHOR")
        rows = [anchor, row("1", "MANY"), row("2", "MANY")]
        units = {"gid://shopify/Product/1": 10, "gid://shopify/Product/2": 10}
        pool = self._pools(rows, units)[anchor["product_id"]]
        assert pool[0]["popularity"] == 1.0

    def test_works_with_no_units_at_all(self):
        """Before build_blocks has ever run, pools are content-only."""
        anchor = row("0", "ANCHOR")
        pool = self._pools([anchor, row("1", "OTHER")], {})[anchor["product_id"]]
        assert pool[0]["popularity"] == 0.0


class TestStyleUnitsFromBuildBlocks:
    """
    build_blocks can see every ACTIVE product, so its map counts a sold-out
    colorway's sales as demand for the style. Deriving from the eligible rows
    cannot, which is why the map is passed through rather than recomputed.
    """

    def test_a_supplied_map_is_used_instead_of_deriving(self):
        anchor = row("0", "ANCHOR")
        rows = [anchor, row("1", "TARGET")]
        # No per-product units at all: only the supplied map knows about sales.
        pools = similarity.build_pools(
            rows, units={}, style_units={"TARGET": 40, "ANCHOR": 10}
        )
        assert pools[anchor["product_id"]][0]["popularity"] == 1.0

    def test_the_scale_ignores_styles_with_no_eligible_colorway(self):
        """
        A style that sold well but has nothing showable must not set an
        unreachable top of the scale — that is the 499-unit ghost again, in a
        different disguise.
        """
        anchor = row("0", "ANCHOR")
        rows = [anchor, row("1", "TARGET")]
        pools = similarity.build_pools(
            rows,
            units={},
            style_units={"TARGET": 40, "SOLD OUT STYLE": 400},
        )
        assert pools[anchor["product_id"]][0]["popularity"] == 1.0

    def test_an_empty_map_is_not_treated_as_missing(self):
        """
        {} means "build_blocks ran and nothing sold", which is different from
        None meaning "no map was written". Neither should crash.
        """
        anchor = row("0", "ANCHOR")
        pools = similarity.build_pools(
            [anchor, row("1", "OTHER")], units={"gid://shopify/Product/1": 5},
            style_units={},
        )
        assert pools[anchor["product_id"]][0]["popularity"] == 0.0
