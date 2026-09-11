"""
Run the pipeline on demand, from the console.

The same chain cron runs (scripts.nightly), started by a button instead of a
schedule. Wanted after changing the eligibility rule, when waiting until 20:00
Makassar is the wrong answer.

Runs in a background thread and reports progress, because the full chain takes
about three minutes and an HTTP request should not be held open that long.

ONE RUN AT A TIME. Two concurrent chains both publishing to Shopify is the one
genuinely bad outcome here - they would interleave their writes and the shop
would end up with a mixture of two runs.

The lock is per-process, which is correct while the API runs a single worker
(it does). With multiple workers this would need to move to the database or a
lock file.
"""

import subprocess
import sys
import threading
from datetime import datetime, timezone

# Mirrors scripts.nightly so the console can show which step is running.
STEPS = [
    ("fetch_products", "the eligible product list"),
    ("build_features", "the feature table"),
    ("build_blocks", "trending, top selling, new arrivals"),
    ("build_pools", "content similarity pools"),
    ("build_copurchase", "co-purchase reranking"),
    ("publish_all", "write everything to Shopify"),
    ("attribute_orders", "attribute orders to the block that led to them"),
]

SLOW_STEP = "build_copurchase"

_lock = threading.Lock()
_state = {
    "running": False,
    "step": None,
    "step_number": 0,
    "total_steps": len(STEPS),
    "started_at": None,
    "finished_at": None,
    "ok": None,
    "error": None,
    "skipped_copurchase": False,
}


def status() -> dict:
    """A snapshot. Copied, so a caller cannot see it change mid-read."""
    with _lock:
        return dict(_state)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(steps: list[tuple[str, str]]) -> None:
    for index, (module, what) in enumerate(steps, start=1):
        with _lock:
            _state["step"] = f"{module} - {what}"
            _state["step_number"] = index

        result = subprocess.run(
            [sys.executable, "-m", f"scripts.{module}"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # Stop at the first failure. A half-finished chain must not
            # publish: pools built from a stale product list look current and
            # are not.
            with _lock:
                _state["running"] = False
                _state["ok"] = False
                _state["finished_at"] = _now()
                _state["error"] = (
                    f"{module} failed. " + (result.stderr or result.stdout)[-600:]
                )
            return

    with _lock:
        _state["running"] = False
        _state["ok"] = True
        _state["step"] = None
        _state["finished_at"] = _now()
        _state["error"] = None


def start(skip_copurchase: bool = False) -> dict:
    """
    Begin a run, unless one is already going.

    Returns the status either way; `started` says which happened, so the
    console can tell "yours is running" from "someone else's already is".
    """
    steps = [s for s in STEPS if not (skip_copurchase and s[0] == SLOW_STEP)]

    with _lock:
        if _state["running"]:
            return {**_state, "started": False}

        _state.update(
            running=True,
            step="starting",
            step_number=0,
            total_steps=len(steps),
            started_at=_now(),
            finished_at=None,
            ok=None,
            error=None,
            skipped_copurchase=skip_copurchase,
        )
        snapshot = dict(_state)

    threading.Thread(target=_run, args=(steps,), daemon=True).start()
    return {**snapshot, "started": True}
