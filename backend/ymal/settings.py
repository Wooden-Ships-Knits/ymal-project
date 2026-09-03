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
INVENTORY_PAGE_SIZE = 50

# ------------------------------------------------------------------
# Eligibility rule  (docs/logic.md §4.1)
# ------------------------------------------------------------------
# A product is eligible ("unfix") only if BOTH hold:
#   1. stocked at the Bali production location  -> replenishable
#   2. title does NOT carry the *SALE* marker   -> not markdown

# Matched case-insensitively as a substring, because the exact location name in
# Shopify is unconfirmed ("Bali", "Bali Warehouse", ...). Run the locations
# script to see the real names, then tighten this.
BALI_LOCATION_PATTERN = "bali"

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

# Beyond the two stated conditions: a product with no online-store URL has
# nowhere to link, so recommending it produces a dead card.
# Set False to apply the literal two-condition rule only.
EXCLUDE_UNPUBLISHED = True

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DATA_DIR = BACKEND_ROOT / "data"
PHASE1_DIR = DATA_DIR / "phase1"
