"""
Does the tracking endpoint actually work from outside?

Written after tracking was installed and recorded nothing for want of three
separate things, every one of which failed silently. The block rendered, no
console error appeared, and Analytics read zero - which is indistinguishable
from "nobody has clicked yet". This turns that silence into a sentence.

verdict() is pure so every failure mode can be tested without a network. probe()
is the thin part that makes the request.
"""

from ymal import tracking_health as th

SHOP = "https://www.wooden-ships.com"


class TestHealthy:
    def test_202_with_the_right_origin_echoed_back(self):
        v = th.verdict(202, SHOP, SHOP)
        assert v["ok"] is True

    def test_200_is_also_fine(self):
        assert th.verdict(200, SHOP, SHOP)["ok"] is True

    def test_a_wildcard_origin_counts_as_allowed(self):
        """Not what we configure, but it does work, so do not cry wolf."""
        assert th.verdict(202, "*", SHOP)["ok"] is True


class TestBasicAuth:
    def test_401_names_the_password_as_the_cause(self):
        v = th.verdict(401, None, SHOP)
        assert v["ok"] is False
        assert v["cause"] == "auth"

    def test_403_too(self):
        assert th.verdict(403, None, SHOP)["cause"] == "auth"

    def test_the_hint_says_where_to_fix_it(self):
        """
        The fix is in the VM's nginx, which is not in this repo - so the
        message has to say so, or someone will search the codebase for it.
        """
        v = th.verdict(401, None, SHOP)
        assert "nginx" in v["hint"].lower()


class TestCors:
    def test_reachable_but_origin_not_allowed(self):
        v = th.verdict(202, None, SHOP)
        assert v["ok"] is False
        assert v["cause"] == "cors"

    def test_a_different_origin_echoed_back_is_still_wrong(self):
        """
        Exactly the bug: the allowlist said woodenships.com and the shop is
        wooden-ships.com, so the header came back naming someone else.
        """
        v = th.verdict(202, "https://www.woodenships.com", SHOP)
        assert v["cause"] == "cors"

    def test_the_hint_names_the_setting(self):
        assert "YMAL_STOREFRONT_ORIGINS" in th.verdict(202, None, SHOP)["hint"]


class TestOtherFailures:
    def test_no_status_means_unreachable(self):
        v = th.verdict(None, None, SHOP)
        assert v["ok"] is False
        assert v["cause"] == "unreachable"

    def test_a_404_is_reported_as_the_wrong_path(self):
        assert th.verdict(404, None, SHOP)["cause"] == "missing"

    def test_503_is_the_store_not_the_route(self):
        """The API answered; it just cannot save. Different fix entirely."""
        assert th.verdict(503, SHOP, SHOP)["cause"] == "storage"

    def test_an_unexpected_status_is_still_a_failure_with_the_code_in_it(self):
        v = th.verdict(418, SHOP, SHOP)
        assert v["ok"] is False
        assert "418" in v["hint"]


class TestSummary:
    def test_a_healthy_probe_reads_as_one_line(self):
        assert th.describe(th.verdict(202, SHOP, SHOP)).startswith("OK:")

    def test_a_failure_reads_as_a_warning(self):
        assert th.describe(th.verdict(401, None, SHOP)).startswith("WARNING:")


class TestProbe:
    def test_a_connection_error_is_unreachable_not_a_crash(self, monkeypatch):
        """
        The probe runs at API startup. A DNS failure or a reload mid-request
        must not take the console down with it.
        """
        def boom(*args, **kwargs):
            raise OSError("name resolution failed")

        monkeypatch.setattr(th.requests, "post", boom)
        v = th.probe("https://example.invalid/api/events", SHOP)
        assert v["cause"] == "unreachable"
        assert "name resolution failed" in v["detail"]

    def test_sends_text_plain_so_it_tests_what_the_beacon_sends(self, monkeypatch):
        sent = {}

        class Response:
            status_code = 202
            headers = {"Access-Control-Allow-Origin": SHOP}

        def fake_post(url, **kwargs):
            sent.update(kwargs)
            return Response()

        monkeypatch.setattr(th.requests, "post", fake_post)
        th.probe("https://x/api/events", SHOP)
        assert sent["headers"]["Content-Type"].startswith("text/plain")
        assert sent["headers"]["Origin"] == SHOP

    def test_sends_an_empty_batch_so_the_probe_stores_nothing(self, monkeypatch):
        sent = {}

        class Response:
            status_code = 202
            headers = {}

        monkeypatch.setattr(
            th.requests, "post", lambda url, **kw: (sent.update(kw), Response())[1]
        )
        th.probe("https://x/api/events", SHOP)
        assert sent["data"] == '{"events":[]}'
