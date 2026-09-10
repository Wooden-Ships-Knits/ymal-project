"""
Central configuration.

Everything tunable lives here rather than in the pipeline code, so the
eligibility rule can be adjusted without editing logic.
"""

from pathlib import Path

# ------------------------------------------------------------------
# Shopify
# ------------------------------------------------------------------
SHOP = "wooden-ships.myshopify.com"
API_VERSION = "2026-01"
GRAPHQL_URL = f"https://{SHOP}/admin/api/{API_VERSION}/graphql.json"

# Admin GraphQL is cost-based. Pause when the remaining budget drops below
# this, so a long paginated run doesn't get throttled mid-flight.
THROTTLE_FLOOR = 200
THROTTLE_SLEEP_SECONDS = 2.0

# Page sizes. Conservative on purpose — nested connections multiply query cost
# and Shopify caps a single query at 1000 points.
PRODUCTS_PAGE_SIZE = 100
# LOCATION_INVENTORY_QUERY has no nested connections (just scalar/object
# fields per node), so its per-node cost is low enough to page at Shopify's
# connection max and cut round-trips ~5x versus 50.
INVENTORY_PAGE_SIZE = 250

# ACTIVE_PRODUCTS_WITH_BALI_STOCK_QUERY (catalog.py) joins each active
# product to its own Bali-location stock via InventoryItem.inventoryLevel,
# a scalar field rather than a connection, in one pass — instead of
# separately paging every product stocked at Bali regardless of status
# (~6,300+, most inactive). It still nests a `variants` connection inside
# `products`, and nested connections multiply query cost.
#
# Measured live (2026-09-03) at 100/100: requestedQueryCost ~353,
# actualQueryCost ~83, against a throttle bucket of 20,000 restoring at
# 1000/sec on this shop's app credentials - nowhere near the cap most
# public apps are limited to. VARIANTS_PAGE_SIZE must stay above this
# catalog's max variants-per-product (observed 44) or inventory silently
# gets truncated for the missed variants, which can misclassify a product
# as "fixed" (not at Bali) if the Bali-stocked variant is one that got cut.
# 100 leaves headroom above the observed max; re-check if it's ever hit.
PRODUCTS_WITH_STOCK_PAGE_SIZE = 100
VARIANTS_PAGE_SIZE = 100

# ------------------------------------------------------------------
# Eligibility rule  (docs/logic.md §4.1)
# ------------------------------------------------------------------
# A product is eligible ("unfix") only if BOTH hold:
#   1. stocked at the Bali production location  -> replenishable
#   2. title does NOT carry the *SALE* marker   -> not markdown

# Matched case-insensitively as a substring. Confirmed against the real
# Shopify locations: "Bali To Produce" is the production location that makes
# a product "unfix" (or "o4" once on *SALE*). "Bali Stock" and "NE-First
# Choice" are separate fixed-stock locations ("fixed" / "sale_stock") and
# must NOT match here, so the pattern is the full name rather than just
# "bali".
BALI_LOCATION_PATTERN = "bali to produce"

# True  -> Bali must hold available quantity > 0.
# False -> it is enough that Bali is an assigned location, meaning the product
#          can be produced there even at zero on-hand.
# Default False: "can be produced" is what unfix means.
REQUIRE_BALI_QUANTITY = False

# The sale marker is asterisk-delimited in product titles.
# Matched by literal containment, never regex — "*" is a regex metacharacter,
# so a compiled "*SALE*" pattern would not mean what it appears to.
SALE_MARKER = "*SALE*"
SALE_MARKER_CASE_SENSITIVE = False

# When True, sale-marked active products are excluded directly in the
# Shopify products query (`NOT title:*SALE*`) instead of being fetched and
# classified locally. Faster - fewer products round-tripped, and no
# inventory lookup wasted on products that are ineligible regardless of
# stock - but active_products.csv then only covers non-sale active
# products: the "sale_marker" / "fixed_stock + sale_marker" audit rows are
# gone, replaced by a single excluded count in the run's console output.
# Verified 2026-09-03: server-side "title:*SALE*" matched has_sale_marker()
# exactly (118/118 products, same set) for this shop's titles. Re-verify if
# SALE_MARKER changes, since Shopify's search wildcarding and the Python
# substring check are different implementations that happen to agree here.
SKIP_SALE_MARKED_IN_QUERY = False

# Beyond the two stated conditions: some products are not the kind of thing a
# recommendation widget should ever surface. A GIFT CARD passes the stated rule
# cleanly - it is stocked at Bali To Produce, carries no *SALE* marker and is
# published - and would have appeared in the widget (product 10208889354, found
# 2026-09-04).
#
# Matched on productType, normalised to lowercase with non-alphanumerics
# stripped, then compared as a PREFIX - so "Gift Card", "Gift Cards" and
# "gift-cards" all match "giftcard". Prefix rather than exact because this
# shop's productType values are inconsistent (V-Neck / V-neck / Vneck all
# occur), and a new spelling should not silently re-open the hole.
EXCLUDED_PRODUCT_TYPE_PREFIXES = ("giftcard",)

# Every real garment on this shop carries a productType - Crewneck, Cardigan,
# V-Neck, Hoodie, Cowlneck, Mock Neck. A blank one means it is not a garment:
# "Front & Back Placement Add-on" (product 7785812426800) is a customisation
# service that sold 97 units in a fortnight and would have topped a raw-volume
# Trending list. Requiring a type is a more general guard than naming each one.
REQUIRE_PRODUCT_TYPE = True

# Beyond the two stated conditions: a product with no online-store URL has
# nowhere to link, so recommending it produces a dead card.
# Set False to apply the literal two-condition rule only.
EXCLUDE_UNPUBLISHED = True

# ------------------------------------------------------------------
# Orders  (Trending, Top Selling)
# ------------------------------------------------------------------
# Orders nest a lineItems connection, and nested connections multiply GraphQL
# cost. Measured live 2026-09-04 on this shop: 100 x 20 costs 119 requested /
# 38 actual against a 20,000 bucket restoring at 1000/s - nowhere near the
# 1000-point per-query cap. Paging at 100 instead of 20 cuts ~3,000 orders from
# 150 round-trips to 30.
#
# Largest line-item count observed in a real order was 5, so 20 leaves ample
# headroom. Orders that hit the limit are reported by units_sold() rather than
# silently undercounted.
ORDERS_PAGE_SIZE = 100
ORDER_LINE_ITEMS_PAGE_SIZE = 20

# Trending = RISING, not raw volume (decided 2026-09-04). Raw 14-day and
# 90-day rankings return nearly the same products, and two blocks showing one
# list looks broken to a shopper.
#
# So: compare this window against the one before it. A product selling 20 units
# after 4 last fortnight is trending; one selling a steady 40 is Top Selling.
TRENDING_WINDOW_DAYS = 14

# Top Selling: plain volume. Same extract as Trending, one argument apart.
#
# Changed from 90 to 14 days on 2026-09-10, at the web team's request - what is
# selling now, rather than what sold over a season.
#
# This is the SAME window Trending uses, so the two blocks now differ only in
# the question they ask: Trending is rising (this fortnight against the one
# before), Top Selling is raw volume. That is still a real distinction, but the
# lists can converge - measure the overlap after changing it, and if the top
# six are largely the same products, widen this again.
TOP_SELLING_WINDOW_DAYS = 14

# New Arrivals: published within this many days, newest first.
NEW_ARRIVALS_WINDOW_DAYS = 30

# How far back orders can actually be read.
#
# Apps without read_all_orders are capped at 60 days, and Shopify truncates
# SILENTLY - a 90-day ranking built on 60 days of data looks perfectly
# plausible and is wrong. That risk drove much of the early planning here.
#
# Measured on this shop 2026-09-04: order history is NOT capped. Line items
# come back intact from 100, 200 and 400 days ago, so these credentials already
# carry full order access. Set to a number to re-impose a guard if that ever
# changes; None means no limit and callers skip the check.
ORDER_HISTORY_CAP_DAYS = None

# A product must sell at least this many units in the CURRENT window to be
# considered at all. Without it, 1 unit -> 3 units is an infinite-looking rise
# and noise tops the list.
TRENDING_MIN_UNITS = 3

# Growth is (now + k) / (before + k). The constant keeps a product with zero
# prior sales from scoring infinity, and damps small numbers generally. Raise
# it to favour established movers, lower it to favour new arrivals.
TRENDING_SMOOTHING = 2.0

# Store more than we display: the gate, the anchor exclusion and colorway
# dedupe all remove items at render, and a list stored at its display length
# arrives thin.
STORED_LIST_DEPTH = 30

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DATA_DIR = BACKEND_ROOT / "data"
PHASE1_DIR = DATA_DIR / "phase1"

# ------------------------------------------------------------------
# Content similarity  (Phase 3, docs/logic.md sections 1-3)
# ------------------------------------------------------------------
# What makes two products "related", agreed with the web team 2026-09-08.
# All four facets matter; season is a hard filter rather than a score.
# Recorded in caveats.md section 6 so the criteria can be revisited.
#
# A tag joins a facet if it CONTAINS one of these keywords, matched on the
# normalised (lowercased, de-pluralised) tag. Substring rather than exact
# because this catalog writes "chunky blend", "chunky tag" and "chunky-vo" for
# the same idea.
SIMILARITY_FACETS = {
    "motif": (
        "graphic", "stripe", "football", "word", "solid", "inset",
        "fair isle", "print", "floral", "heart", "star", "flag", "skull",
    ),
    "fabric": (
        "cotton", "wool", "chunky", "lightweight", "blend", "cashmere",
        "linen", "jersey",
    ),
    "colour": (
        "neutral", "dark", "white", "black", "grassy", "blue", "red",
        "green", "pink", "brown", "grey", "gray", "bright",
    ),
}

# How much each facet contributes. Silhouette is not tag-based - it comes from
# product_type_normalised - so it is scored separately but weighted here.
# They need not sum to 1; scores are comparable within one anchor's pool, which
# is all ranking needs.
SIMILARITY_WEIGHTS = {
    "motif": 3.0,       # the most visible thing a shopper matches on
    "fabric": 2.0,      # chunky next to lightweight looks wrong
    "colour": 1.5,
    "silhouette": 1.5,  # crew with crew, v-neck with v-neck
}

# Hard rule: a recommendation must be in the same season as the anchor.
# Decided 2026-09-08. Halves the candidate pool (152 autumn / 102 spring), so
# revisit if pools come out thin.
REQUIRE_SAME_SEASON = True

# Products with no season tag (4 of 258 on 2026-09-08) would match nothing
# under the rule above. They fall back to ignoring season rather than shipping
# an empty pool.
SEASONLESS_IGNORES_SEASON = True

# How deep to store. STORED_LIST_DEPTH above is the general rule; pools use the
# same number for the same reason - the gate, the anchor exclusion and the
# colorway dedupe all remove items at render.
POOL_DEPTH = STORED_LIST_DEPTH

# ------------------------------------------------------------------
# Co-purchase  (Phase 4)
# ------------------------------------------------------------------
# A full seasonal cycle, so autumn pairs are learned from last autumn too.
# Season is a hard filter at render, so stale cross-season pairs are removed
# anyway rather than needing a shorter window.
COPURCHASE_WINDOW_DAYS = 365

# The baskets query asks for product ids and nothing else - no createdAt, no
# quantity, no order id. Measured live 2026-09-08: at 250 orders x 20 line
# items it costs 145 requested / 46 actual against a 20,000 bucket, and a
# 250-order page returns in ~0.6s versus ~1.16s for a 100-order page. Paging at
# Shopify's connection maximum is both cheaper per order and faster per
# request, so the win is fewer round trips rather than fewer fields.
BASKETS_PAGE_SIZE = 250

# A pair must appear in at least this many baskets to score. Below it, lift is
# dominated by coincidence - two products bought together once say nothing.
COPURCHASE_MIN_PAIRS = 3

# How much co-purchase may move a product within its content pool. Reranking
# only: content similarity decides who is in the 30, this decides the order.
# At 0.5 a maximally co-purchased pair can lift a candidate by 50%.
COPURCHASE_RERANK_WEIGHT = 0.5
