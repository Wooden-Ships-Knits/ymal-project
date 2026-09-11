"""
Content similarity. Pure scoring, so all of it runs offline.

A wrong score is invisible until a customer sees a bad recommendation, which
is why the ranking rules get direct tests rather than being trusted.
"""

from ymal import settings, similarity


def row(pid, title, style, tags, season="autumn", ptype="crewneck",
        collections=None):
    return {
        "product_id": pid,
        "product_gid": "gid://shopify/Product/" + pid,
        "handle": title.lower().replace(" ", "-"),
        "title": title,
        "style_key": style,
        "product_type_normalised": ptype,
        "season": season,
        "signal_tags": tags,
        "collections": collections or [],
    }


def test_a_plural_collapses_onto_its_singular():
    # stripe/stripes are separate tags in this catalog. Left alone, two
    # products sharing both look twice as similar as they are.
    vocab = {"stripe", "stripes"}
    assert similarity.depluralise("stripes", vocab) == "stripe"


def test_a_word_ending_in_s_is_not_mangled():
    # "dress" must not become "dres".
    assert similarity.depluralise("dress", {"dress"}) == "dress"


def test_facets_match_on_substring():
    assert similarity.facet_of("chunky blend") == "fabric"
    assert similarity.facet_of("cotton-vo") == "fabric"
    assert similarity.facet_of("stripe") == "motif"
    assert similarity.facet_of("neutral") == "colour"
    assert similarity.facet_of("ess 2026 release") is None


def test_a_rare_tag_outweighs_a_common_one():
    # Nearly everything is cotton; almost nothing is football.
    tag_sets = [{"cotton", "football"}] + [{"cotton"} for _ in range(99)]
    idf = similarity.inverse_document_frequency(tag_sets)

    assert idf["football"] > idf["cotton"]


def test_identical_tag_sets_score_higher_than_disjoint_ones():
    idf = {"a": 1.0, "b": 1.0}

    assert similarity.weighted_jaccard({"a"}, {"a"}, idf) == 1.0
    assert similarity.weighted_jaccard({"a"}, {"b"}, idf) == 0.0


def test_empty_tag_sets_do_not_divide_by_zero():
    assert similarity.weighted_jaccard(set(), set(), {}) == 0.0


def test_a_pool_never_contains_the_anchors_own_style():
    rows = [
        row("1", "CHARLOTTE CREW", "CHARLOTTE CREW", ["stripe", "cotton"]),
        row("2", "CHARLOTTE CREW", "CHARLOTTE CREW", ["stripe", "cotton"]),
        row("3", "ARDEN CREW", "ARDEN CREW", ["stripe", "cotton"]),
    ]
    pools = similarity.build_pools(rows)

    assert [c["style_key"] for c in pools["1"]] == ["ARDEN CREW"]


def test_a_pool_shows_one_product_per_style():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe", "cotton"]),
        row("2", "ARDEN CREW", "ARDEN CREW", ["stripe", "cotton"]),
        row("3", "ARDEN CREW", "ARDEN CREW", ["stripe", "cotton"]),
    ]
    pools = similarity.build_pools(rows)

    assert len(pools["1"]) == 1


def test_a_different_season_is_excluded():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"], season="autumn"),
        row("2", "SPRING THING", "SPRING THING", ["stripe"], season="spring"),
    ]
    pools = similarity.build_pools(rows)

    assert pools["1"] == []


def test_a_product_with_no_season_still_gets_a_pool():
    # 4 of 258 products carry no season tag. Under a hard season rule they
    # would match nothing, so they ignore it rather than ship an empty pool.
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"], season=None),
        row("2", "OTHER", "OTHER", ["stripe"], season="spring"),
    ]
    pools = similarity.build_pools(rows)

    assert len(pools["1"]) == 1


def test_the_same_silhouette_scores_higher():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"], ptype="crewneck"),
        row("2", "SAME SHAPE", "SAME SHAPE", ["stripe"], ptype="crewneck"),
        row("3", "OTHER SHAPE", "OTHER SHAPE", ["stripe"], ptype="vneck"),
    ]
    pools = similarity.build_pools(rows)

    assert pools["1"][0]["title"] == "SAME SHAPE"


def test_pools_are_capped_at_the_requested_depth():
    rows = [row("1", "ANCHOR", "ANCHOR", ["stripe"])]
    rows += [row(str(i), f"P{i}", f"P{i}", ["stripe"]) for i in range(2, 20)]

    pools = similarity.build_pools(rows, depth=5)

    assert len(pools["1"]) == 5


def test_ties_break_deterministically():
    # Two runs must produce the same list, or a "nothing changed" diff is noise.
    rows = [row("1", "ANCHOR", "ANCHOR", ["stripe"])]
    rows += [row(str(i), f"P{i}", f"P{i}", ["stripe"]) for i in range(2, 8)]

    first = similarity.build_pools(rows)["1"]
    second = similarity.build_pools(rows)["1"]

    assert [c["product_id"] for c in first] == [c["product_id"] for c in second]


def test_a_clean_set_of_pools_passes_the_self_check():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe", "cotton"]),
        row("2", "OTHER", "OTHER", ["stripe", "cotton"]),
    ]
    pools = similarity.build_pools(rows)

    assert similarity.check(rows, pools) == []


def test_an_empty_pool_is_caught():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"], season="autumn"),
        row("2", "OTHER", "OTHER", ["stripe"], season="spring"),
    ]
    pools = similarity.build_pools(rows)

    assert any("empty pool" in p for p in similarity.check(rows, pools))


# ------------------------------------------------------------------
# Collections and popularity
# ------------------------------------------------------------------

def test_a_shared_collection_lifts_a_candidate():
    # Collections are the merchandiser's own grouping, so sharing one is real
    # evidence that two products belong together.
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"], collections=["game-day"]),
        row("2", "SAME COLLECTION", "SAME COLLECTION", ["stripe"], collections=["game-day"]),
        row("3", "OTHER", "OTHER", ["stripe"], collections=["cardigans"]),
    ]
    pools = similarity.build_pools(rows)

    assert pools["1"][0]["title"] == "SAME COLLECTION"


def test_a_collection_on_everything_is_dropped_before_scoring():
    # 88-100% of this shop's products sit in operational collections like
    # tax-clothing. IDF alone does not neutralise them - its +1.0 floor leaves
    # a universal term at 0.82 against 1.92 for a rare one - so they are
    # removed by frequency instead.
    # "all" is on every product; "game-day" on two of five, which is under the
    # cutoff and so survives.
    rows = [
        row(str(i), f"P{i}", f"P{i}", ["stripe"], collections=["all"])
        for i in range(1, 6)
    ]
    rows[0]["collections"] = ["all", "game-day"]
    rows[1]["collections"] = ["all", "game-day"]

    prepared, idf, collection_idf = similarity.prepare(rows)

    assert "all" not in prepared[0]["_collections"]
    assert "game-day" in prepared[0]["_collections"]


def test_popularity_is_zero_when_nothing_has_sold():
    assert similarity.popularity({}, "gid", 0) == 0.0


def test_popularity_is_square_rooted():
    # One product sells 153 units in a fortnight while most sell single
    # digits. On a linear scale everything else would sit at nearly zero and
    # be indistinguishable.
    assert similarity.popularity({"a": 25}, "a", 100) == 0.5


def test_a_better_seller_ranks_higher_among_equals():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"]),
        row("2", "QUIET", "QUIET", ["stripe"]),
        row("3", "POPULAR", "POPULAR", ["stripe"]),
    ]
    units = {"gid://shopify/Product/2": 1, "gid://shopify/Product/3": 100}

    pools = similarity.build_pools(rows, units=units)

    assert pools["1"][0]["title"] == "POPULAR"


def test_selling_well_does_not_get_an_unrelated_product_into_a_pool():
    # The whole safety argument: content decides membership, popularity only
    # reorders. Otherwise every pool collapses onto the same bestsellers.
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"]),
        row("2", "RELATED", "RELATED", ["stripe"]),
        row("3", "UNRELATED", "UNRELATED", ["nothing-in-common"], ptype="cardigan"),
    ]
    units = {"gid://shopify/Product/3": 10000}

    pools = similarity.build_pools(rows, units=units)

    assert [c["title"] for c in pools["1"]] == ["RELATED"]


def test_pools_still_build_without_any_sales_data():
    # build_pools may run before build_blocks has ever written units.json.
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"]),
        row("2", "OTHER", "OTHER", ["stripe"]),
    ]
    pools = similarity.build_pools(rows, units=None)

    assert len(pools["1"]) == 1
    assert pools["1"][0]["popularity"] == 0.0
