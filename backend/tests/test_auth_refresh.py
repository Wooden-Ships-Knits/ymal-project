"""
The Admin API token must never be allowed to go stale.

Found 2026-09-15: the console's Ranking tab showed
"401 Client Error: Unauthorized". The client_credentials grant issues tokens
that expire after 24 hours (expires_in: 86399), and auth.get_token() cached the
first one for the life of the process, with nothing ever calling force_refresh.
The api container is long-running, so 24 hours after `docker compose up` every
console screen that reads Shopify failed until the container was restarted.

The nightly job never noticed: `docker compose run --rm api` starts a fresh
process, and a fresh process gets a fresh token. That is what made it look
unrelated to anything the pipeline does.

Two defences, both tested here:
  1. refresh BEFORE expiry, from the expires_in Shopify returns
  2. on a 401 anyway, fetch a new token once and retry - never loop
"""

import pytest

from ymal import auth, shopify


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            import requests
            err = requests.HTTPError(f"{self.status_code} Client Error")
            err.response = self
            raise err


@pytest.fixture(autouse=True)
def clean_auth(monkeypatch):
    """Module-level cache must not leak between tests."""
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "id")
    monkeypatch.setenv("SHOPIFY_SECRET_KEY", "secret")
    monkeypatch.setattr(auth, "_cached_token", None)
    monkeypatch.setattr(auth, "_token_expires_at", 0.0)
    yield


@pytest.fixture
def clock(monkeypatch):
    """A controllable clock, so expiry is tested without waiting 24 hours."""
    state = {"now": 1_000_000.0}
    monkeypatch.setattr(auth.time, "time", lambda: state["now"])
    return state


@pytest.fixture
def token_server(monkeypatch):
    """
    The ONE fake for requests.post, routed by URL.

    auth and shopify import the same `requests` module
    (`auth.requests is shopify.requests`). The first version of these tests
    patched requests.post twice - once for the token exchange, once for GraphQL
    - and the second silently replaced the first, so the token exchange hit the
    GraphQL fake and every retry test failed for a reason unrelated to the code.
    Hands out tok-1, tok-2, ... and counts exchanges.
    """
    state = {"calls": 0, "expires_in": 86399, "graphql": None}

    def post(url, **kwargs):
        if url == auth.TOKEN_URL:
            state["calls"] += 1
            payload = {"access_token": f"tok-{state['calls']}"}
            if state["expires_in"] is not None:
                payload["expires_in"] = state["expires_in"]
            return FakeResponse(200, payload)
        if state["graphql"] is None:
            raise AssertionError(f"unexpected POST to {url}")
        return state["graphql"](url, **kwargs)

    monkeypatch.setattr(auth.requests, "post", post)
    return state


class TestTokenLifetime:
    def test_a_fresh_token_is_reused(self, clock, token_server):
        assert auth.get_token() == "tok-1"
        assert auth.get_token() == "tok-1"
        assert token_server["calls"] == 1

    def test_reused_right_up_to_the_safety_margin(self, clock, token_server):
        auth.get_token()
        clock["now"] += 86399 - auth.REFRESH_MARGIN_SECONDS - 1
        assert auth.get_token() == "tok-1"
        assert token_server["calls"] == 1

    def test_refreshed_before_it_expires(self, clock, token_server):
        """
        The bug: a 24-hour token cached forever. It must be replaced while it
        is still valid, not after Shopify has started refusing it.
        """
        auth.get_token()
        clock["now"] += 86399 - auth.REFRESH_MARGIN_SECONDS + 1
        assert auth.get_token() == "tok-2"
        assert token_server["calls"] == 2

    def test_long_after_expiry_it_is_certainly_refreshed(self, clock, token_server):
        """The exact situation on the VM: days after the container started."""
        auth.get_token()
        clock["now"] += 3 * 86400
        assert auth.get_token() == "tok-2"

    def test_force_refresh_always_fetches(self, clock, token_server):
        auth.get_token()
        assert auth.get_token(force_refresh=True) == "tok-2"

    def test_a_missing_expires_in_is_treated_as_short_lived(self, clock, token_server):
        """
        Assuming "never expires" is the original bug. With no lifetime given,
        assume a short one and refresh often, rather than trusting it forever.
        """
        token_server["expires_in"] = None
        auth.get_token()
        clock["now"] += auth.DEFAULT_LIFETIME_SECONDS + 1
        assert auth.get_token() == "tok-2"


class TestGraphqlRetriesOnce:
    def _patch_graphql(self, token_server, statuses):
        """GraphQL requests return these statuses in order."""
        seen = {"calls": 0, "tokens": []}

        def post(url, headers=None, **kwargs):
            seen["tokens"].append(headers["X-Shopify-Access-Token"])
            status = statuses[seen["calls"]]
            seen["calls"] += 1
            if status == 200:
                return FakeResponse(200, {"data": {"shop": {"name": "Wooden Ships"}}})
            return FakeResponse(status, {"errors": "Unauthorized"})

        token_server["graphql"] = post
        return seen

    def test_a_401_gets_a_new_token_and_succeeds(self, monkeypatch, clock, token_server):
        """
        Shopify can refuse a token before we expected - revoked, secret rotated,
        clock skew. One retry with a freshly issued token recovers it.
        """
        seen = self._patch_graphql(token_server, [401, 200])
        data = shopify.graphql("{ shop { name } }")
        assert data == {"shop": {"name": "Wooden Ships"}}
        assert seen["calls"] == 2
        assert seen["tokens"] == ["tok-1", "tok-2"]

    def test_a_second_401_raises_instead_of_looping(self, monkeypatch, clock, token_server):
        """
        If a brand-new token is refused too, the credentials themselves are
        wrong. Retrying forever would hide that and hammer Shopify.
        """
        import requests

        seen = self._patch_graphql(token_server, [401, 401])
        with pytest.raises(requests.HTTPError):
            shopify.graphql("{ shop { name } }")
        assert seen["calls"] == 2

    def test_other_errors_are_not_retried(self, monkeypatch, clock, token_server):
        """A 500 is not an auth problem; a new token would not fix it."""
        import requests

        seen = self._patch_graphql(token_server, [500])
        with pytest.raises(requests.HTTPError):
            shopify.graphql("{ shop { name } }")
        assert seen["calls"] == 1
        assert token_server["calls"] == 1
