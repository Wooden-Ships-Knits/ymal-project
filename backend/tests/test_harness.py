"""
Proves the test harness can import the package under test.

Not a placeholder: `ymal` importing cleanly from `backend/` is the thing every
other test file assumes, and it is worth one test that says so out loud.
"""

def test_ymal_package_imports():
    from ymal import settings

    assert settings.SHOP == "wooden-ships.myshopify.com"
