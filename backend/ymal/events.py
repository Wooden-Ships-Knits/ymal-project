"""
Storefront tracking events - impressions, clicks, add-to-cart.

Phase 6. This is the training data for Phase 8 and CANNOT be collected
retroactively, so it is worth getting the shape right before any of it is
recorded.

The validation here is deliberately strict, because POST /api/events is the
only unauthenticated write in the project: shoppers' browsers call it with no
credentials. Anything unrecognised is rejected rather than stored.

NO PERSONAL DATA. A session id is a random string the browser generates for
itself and never reveals to anyone; it exists to tell one visit's events apart
from another's, and nothing here can be traced back to a person.

Pure functions, no I/O.
"""

EVENT_TYPES = ("impression", "click", "add_to_cart")

BLOCK_IDS = (
    "featured",
    "trending",
    "top_selling",
    "new_arrivals",
    "recently_viewed",
)

PAGE_TYPES = (
    "product", "home", "cart", "collection", "search",
    "not_found", "blog", "account", "thank_you",
)

# A batch is one beacon. Generous enough for a page with several blocks, small
# enough that a malformed or hostile caller cannot post a megabyte.
MAX_BATCH = 50
MAX_HANDLE = 255
MAX_SESSION = 64
MAX_POSITION = 100


def validate(event: object) -> list[str]:
    """Every problem with one event. Empty means it may be stored."""
    if not isinstance(event, dict):
        return ["event must be an object"]

    problems = []

    if event.get("type") not in EVENT_TYPES:
        problems.append(f"type must be one of: {', '.join(EVENT_TYPES)}")

    if event.get("block") not in BLOCK_IDS:
        problems.append("block is not a known block")

    if event.get("page_type") not in PAGE_TYPES:
        problems.append("page_type is not a known page template")

    session = event.get("session")
    if not isinstance(session, str) or not 1 <= len(session) <= MAX_SESSION:
        problems.append(f"session must be a string of 1 to {MAX_SESSION} characters")

    # A handle identifies the product. Impressions carry the whole row, so they
    # are the one event type that may omit it.
    handle = event.get("handle")
    if event.get("type") == "impression":
        if handle is not None and not _is_handle(handle):
            problems.append("handle must be a string of 1 to 255 characters")
    elif not _is_handle(handle):
        problems.append("handle is required for this event type")

    position = event.get("position")
    if position is not None:
        if not isinstance(position, int) or isinstance(position, bool):
            problems.append("position must be an integer")
        elif not 1 <= position <= MAX_POSITION:
            problems.append(f"position must be between 1 and {MAX_POSITION}")

    anchor = event.get("anchor")
    if anchor is not None and not _is_handle(anchor):
        problems.append("anchor must be a string of 1 to 255 characters")

    return problems


def _is_handle(value: object) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= MAX_HANDLE


def clean_batch(events: object) -> tuple[list[dict], list[str]]:
    """
    Keep the events that validate, and say what was wrong with the rest.

    A partly-bad batch is accepted rather than rejected whole: one malformed
    event should not lose the others in the same beacon, and the browser has no
    way to retry.
    """
    if not isinstance(events, list):
        return [], ["events must be a list"]

    if len(events) > MAX_BATCH:
        return [], [f"at most {MAX_BATCH} events per request"]

    good = []
    problems = []
    for index, event in enumerate(events):
        found = validate(event)
        if found:
            problems.append(f"[{index}] " + "; ".join(found))
        else:
            good.append(normalise(event))
    return good, problems


def normalise(event: dict) -> dict:
    """
    Reduce an event to exactly the columns we store.

    Anything else the browser sent is dropped here rather than stored - an
    endpoint that keeps unknown fields is how personal data arrives by
    accident.
    """
    return {
        "type": event["type"],
        "block": event["block"],
        "page_type": event["page_type"],
        "session": event["session"],
        "handle": event.get("handle"),
        "anchor": event.get("anchor"),
        "position": event.get("position"),
    }
