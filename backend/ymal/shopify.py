"""
Thin Admin GraphQL client: one request helper and one pagination helper.

Covers the two things every caller needs and nobody should reimplement —
raising on GraphQL errors (which arrive with HTTP 200, so status alone is not
enough) and backing off before hitting the cost throttle.
"""

import time
from collections.abc import Iterator

import requests

from ymal import auth, settings


class ShopifyGraphQLError(RuntimeError):
    """Shopify returned a GraphQL-level error."""


def graphql(query: str, variables: dict | None = None) -> dict:
    """POST a GraphQL query and return its `data` block."""
    response = requests.post(
        settings.GRAPHQL_URL,
        headers=auth.get_headers(),
        json={"query": query, "variables": variables or {}},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()

    if "errors" in payload:
        raise ShopifyGraphQLError(payload["errors"])

    _respect_throttle(payload)
    return payload["data"]


def _respect_throttle(payload: dict) -> None:
    """Sleep if the remaining query-cost budget is running low."""
    throttle = (
        payload.get("extensions", {}).get("cost", {}).get("throttleStatus", {})
    )
    available = throttle.get("currentlyAvailable")
    if available is not None and available < settings.THROTTLE_FLOOR:
        time.sleep(settings.THROTTLE_SLEEP_SECONDS)


def paginate(
    query: str,
    path: list[str],
    variables: dict | None = None,
) -> Iterator[dict]:
    """
    Yield every node from a cursor-paginated connection.

    `path` is the key sequence from the `data` block down to the connection —
    e.g. ["products"], or ["location", "inventoryLevels"].
    """
    cursor = None
    while True:
        data = graphql(query, {**(variables or {}), "cursor": cursor})

        connection = data
        for key in path:
            if connection is None:
                return
            connection = connection[key]

        yield from (edge["node"] for edge in connection["edges"])

        page_info = connection["pageInfo"]
        if not page_info["hasNextPage"]:
            return
        cursor = page_info["endCursor"]
