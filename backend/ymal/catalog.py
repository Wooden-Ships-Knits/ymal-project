"""
Catalog reads from the Shopify Admin API — locations, active products, and
inventory at a given location.

Note on approach: eligibility needs to know which products are stocked at Bali.
The obvious query — walk every product's variants and their inventory levels —
multiplies GraphQL cost well past Shopify's 1000-point per-query cap. Instead we
query the Bali location's inventory directly and join against the product list.
Two cheap passes instead of one that cannot run.
"""

from ymal import settings
from ymal.eligibility import matches_bali
from ymal.shopify import graphql, paginate

LOCATIONS_QUERY = """
query Locations {
  locations(first: 100, includeInactive: true) {
    edges {
      node {
        id
        name
        isActive
        address { country city }
      }
    }
  }
}
"""

ACTIVE_PRODUCTS_QUERY = """
query ActiveProducts($cursor: String) {
  products(first: %d, after: $cursor, query: "status:active") {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        title
        handle
        status
        onlineStoreUrl
        totalInventory
        productType
        vendor
      }
    }
  }
}
""" % settings.PRODUCTS_PAGE_SIZE

_ACTIVE_PRODUCTS_FILTER = "status:active"
if settings.SKIP_SALE_MARKED_IN_QUERY:
    # Reuses the same marker the Python-side rule checks (has_sale_marker in
    # eligibility.py) so the two filters can't drift apart.
    _ACTIVE_PRODUCTS_FILTER += f" AND NOT title:{settings.SALE_MARKER}"

# Joins each active product directly to its own stock at one location via
# InventoryItem.inventoryLevel(locationId:) - a scalar field, not a
# connection - instead of separately paging that location's entire
# inventory. Nests a `variants` connection though, so page sizes are kept
# small (settings.py) to stay under Shopify's cost cap.
ACTIVE_PRODUCTS_WITH_STOCK_QUERY = """
query ActiveProductsWithStock($cursor: String, $locationId: ID!) {
  products(first: %d, after: $cursor, query: "%s") {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        title
        handle
        status
        onlineStoreUrl
        totalInventory
        productType
        vendor
        variants(first: %d) {
          nodes {
            inventoryItem {
              inventoryLevel(locationId: $locationId) {
                quantities(names: ["available"]) { name quantity }
              }
            }
          }
        }
      }
    }
  }
}
""" % (
    settings.PRODUCTS_WITH_STOCK_PAGE_SIZE,
    _ACTIVE_PRODUCTS_FILTER,
    settings.VARIANTS_PAGE_SIZE,
)

PRODUCTS_COUNT_QUERY = """
query ProductsCount($query: String!) {
  productsCount(query: $query) { count }
}
"""

LOCATION_INVENTORY_QUERY = """
query LocationInventory($id: ID!, $cursor: String) {
  location(id: $id) {
    inventoryLevels(first: %d, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      edges {
        node {
          quantities(names: ["available"]) { name quantity }
          item {
            id
            variant { id product { id } }
          }
        }
      }
    }
  }
}
""" % settings.INVENTORY_PAGE_SIZE


def numeric_id(gid: str) -> str:
    """gid://shopify/Product/123 -> '123'"""
    return gid.rsplit("/", 1)[-1] if gid else ""


def fetch_locations() -> list[dict]:
    """Every location on the shop, active or not."""
    data = graphql(LOCATIONS_QUERY)
    return [edge["node"] for edge in data["locations"]["edges"]]


def find_bali_locations(locations: list[dict] | None = None) -> list[dict]:
    """Locations matching BALI_LOCATION_PATTERN."""
    if locations is None:
        locations = fetch_locations()
    return [loc for loc in locations if matches_bali(loc["name"])]


def fetch_active_products() -> list[dict]:
    """Every product with status ACTIVE."""
    return list(paginate(ACTIVE_PRODUCTS_QUERY, ["products"]))


def fetch_active_products_with_stock(
    location_id: str,
) -> tuple[list[dict], dict[str, int], list[str]]:
    """
    Active products joined with their stock at one location, in one pass.

    Returns (products, stock, truncated_ids). `products`/`stock` have the
    same shapes fetch_active_products()/fetch_stock_by_product() would
    produce, so callers can swap between them freely. Only usable for a
    single location - the join happens per product via
    InventoryItem.inventoryLevel(locationId:), which takes one ID, not a
    list.

    `truncated_ids` lists any product whose variant count hit
    VARIANTS_PAGE_SIZE exactly - a sign its real variant count may be
    higher and got cut off, which can silently misclassify a product as
    "fixed" (not at Bali) if the truncated variants included the
    Bali-stocked one. Callers should surface this rather than trust the
    result silently.
    """
    products = []
    stock: dict[str, int] = {}
    truncated_ids: list[str] = []

    for node in paginate(
        ACTIVE_PRODUCTS_WITH_STOCK_QUERY,
        ["products"],
        {"locationId": location_id},
    ):
        variants = node.pop("variants")["nodes"]
        if len(variants) >= settings.VARIANTS_PAGE_SIZE:
            truncated_ids.append(node["id"])

        levels = [variant["inventoryItem"]["inventoryLevel"] for variant in variants]

        if any(level is not None for level in levels):
            stock[node["id"]] = sum(
                q.get("quantity") or 0
                for level in levels
                if level is not None
                for q in (level.get("quantities") or [])
                if q.get("name") == "available"
            )

        products.append(node)

    return products, stock, truncated_ids


def count_products(query_filter: str) -> int:
    """Count of products matching a Shopify search query string."""
    data = graphql(PRODUCTS_COUNT_QUERY, {"query": query_filter})
    return data["productsCount"]["count"]


def fetch_stock_by_product(location_ids: list[str]) -> dict[str, int]:
    """
    Map product GID -> total available quantity across the given locations.

    Presence of a key means the product is stocked at one of those locations.
    Whether a zero quantity still counts is governed by REQUIRE_BALI_QUANTITY
    in settings — this function reports, it does not judge.
    """
    totals: dict[str, int] = {}

    for location_id in location_ids:
        for level in paginate(
            LOCATION_INVENTORY_QUERY,
            ["location", "inventoryLevels"],
            {"id": location_id},
        ):
            item = level.get("item") or {}
            variant = item.get("variant") or {}
            product = variant.get("product") or {}
            product_id = product.get("id")
            if not product_id:
                continue  # inventory item with no live variant behind it

            available = next(
                (
                    q.get("quantity") or 0
                    for q in (level.get("quantities") or [])
                    if q.get("name") == "available"
                ),
                0,
            )
            totals[product_id] = totals.get(product_id, 0) + available

    return totals
