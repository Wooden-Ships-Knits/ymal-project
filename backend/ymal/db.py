"""
Postgres, for tracking events.

The db container has been running since the first compose file and unused until
now - this is what it was reserved for.

Everything else in this project stores its results as files or Shopify
metafields, deliberately: those are small, and a bad run can be read before it
reaches anything. Events are different. They arrive continuously, they are
never rewritten, and they will outgrow a JSON file within weeks.

Connection details come from DATABASE_URL, which docker-compose already passes
to the api service. Without it the tracking endpoints refuse rather than
pretend to store anything - a beacon that silently drops events is worse than
one that fails, because nobody notices until the Analytics screen is empty.
"""

import os
from contextlib import contextmanager

import psycopg
import psycopg.conninfo
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


class NoDatabase(RuntimeError):
    """DATABASE_URL is not set, so there is nowhere to store events."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id          BIGSERIAL PRIMARY KEY,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  type        TEXT        NOT NULL,
  block       TEXT        NOT NULL,
  page_type   TEXT        NOT NULL,
  session     TEXT        NOT NULL,
  handle      TEXT,
  anchor      TEXT,
  position    INTEGER
);

-- The Analytics screen always groups by block and asks for a date range, so
-- these two are what every query it makes will use.
CREATE INDEX IF NOT EXISTS events_created_at_idx ON events (created_at);
CREATE INDEX IF NOT EXISTS events_block_idx      ON events (block, type);

CREATE TABLE IF NOT EXISTS attributed_orders (
  order_id    TEXT        PRIMARY KEY,
  created_at  TIMESTAMPTZ NOT NULL,
  block       TEXT        NOT NULL,
  total       NUMERIC(12, 2),
  currency    TEXT
);
CREATE INDEX IF NOT EXISTS attributed_orders_block_idx
  ON attributed_orders (block, created_at);
"""


def url() -> str:
    """
    Connection details, assembled from separate parts rather than a URL.

    A password is not URL-safe. This shop's contains a "/", which terminates
    the authority section of a URL and made the host parse as the database
    name - a connection error that reads as a DNS failure and sends you looking
    in the wrong place entirely. make_conninfo quotes each value properly, so
    any password works.

    DATABASE_URL is still honoured when set, for anyone who wants to point this
    at another server - but it must be a real libpq URL, not SQLAlchemy's
    "postgresql+psycopg://" dialect form, which psycopg does not accept.
    """
    explicit = os.getenv("DATABASE_URL", "")
    if explicit:
        return explicit

    password = os.getenv("POSTGRES_PASSWORD", "")
    if not password:
        raise NoDatabase(
            "POSTGRES_PASSWORD is not set, so there is nowhere to store "
            "events. docker-compose passes it to the api service from .env."
        )

    return psycopg.conninfo.make_conninfo(
        host=os.getenv("POSTGRES_HOST", "db"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER", "ymal"),
        password=password,
        dbname=os.getenv("POSTGRES_DB", "ymal"),
    )


def pool() -> ConnectionPool:
    """One pool for the process, opened on first use."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(url(), min_size=1, max_size=4, open=True)
    return _pool


@contextmanager
def connection():
    with pool().connection() as conn:
        yield conn


def migrate() -> None:
    """Create the tables if they are not there. Safe to run on every start."""
    with connection() as conn:
        conn.execute(SCHEMA)


def insert_events(rows: list[dict]) -> int:
    """Store a batch. Returns how many were written."""
    if not rows:
        return 0

    with connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO events
                  (type, block, page_type, session, handle, anchor, position)
                VALUES
                  (%(type)s, %(block)s, %(page_type)s, %(session)s,
                   %(handle)s, %(anchor)s, %(position)s)
                """,
                rows,
            )
    return len(rows)


def summary(days: int = 30) -> list[dict]:
    """
    Per block: impressions, clicks, adds, and the rates between them.

    Rates are computed here rather than in the browser so every caller reads
    the same numbers, and because "clicks over impressions" is only meaningful
    when both come from the same window.
    """
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT block,
                   COUNT(*) FILTER (WHERE type = 'impression')  AS impressions,
                   COUNT(*) FILTER (WHERE type = 'click')       AS clicks,
                   COUNT(*) FILTER (WHERE type = 'add_to_cart') AS adds
              FROM events
             WHERE created_at >= now() - make_interval(days => %s)
             GROUP BY block
             ORDER BY clicks DESC
            """,
            (days,),
        ).fetchall()

    out = []
    for block, impressions, clicks, adds in rows:
        out.append(
            {
                "block": block,
                "impressions": impressions,
                "clicks": clicks,
                "add_to_cart": adds,
                "click_rate": round(clicks / impressions, 4) if impressions else None,
                "add_rate": round(adds / clicks, 4) if clicks else None,
            }
        )
    return out


def revenue(days: int = 30) -> list[dict]:
    """Attributed orders per block, from the nightly order pass."""
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT block, COUNT(*), COALESCE(SUM(total), 0), MAX(currency)
              FROM attributed_orders
             WHERE created_at >= now() - make_interval(days => %s)
             GROUP BY block
             ORDER BY SUM(total) DESC NULLS LAST
            """,
            (days,),
        ).fetchall()

    return [
        {"block": b, "orders": n, "revenue": float(total), "currency": currency}
        for b, n, total, currency in rows
    ]


def totals(days: int) -> dict:
    """
    The headline numbers, and the same numbers for the period before, so the
    console can show which way each is moving.

    Compared against the IMMEDIATELY PRECEDING window of the same length, not
    against a fixed date. "Last 30 days versus the 30 before" is the only
    comparison that holds its meaning as time passes.
    """
    with connection() as conn:
        row = conn.execute(
            """
            WITH windows AS (
              SELECT
                now() - make_interval(days => %(days)s)     AS this_start,
                now() - make_interval(days => %(days)s * 2) AS prev_start
            ),
            ev AS (
              SELECT
                COUNT(*) FILTER (WHERE type='impression'  AND created_at >= w.this_start) AS impressions,
                COUNT(*) FILTER (WHERE type='click'       AND created_at >= w.this_start) AS clicks,
                COUNT(*) FILTER (WHERE type='add_to_cart' AND created_at >= w.this_start) AS adds,
                COUNT(*) FILTER (WHERE type='impression'  AND created_at >= w.prev_start AND created_at < w.this_start) AS prev_impressions,
                COUNT(*) FILTER (WHERE type='click'       AND created_at >= w.prev_start AND created_at < w.this_start) AS prev_clicks,
                COUNT(*) FILTER (WHERE type='add_to_cart' AND created_at >= w.prev_start AND created_at < w.this_start) AS prev_adds
              FROM events, windows w
            ),
            ord AS (
              SELECT
                COUNT(*)                    FILTER (WHERE created_at >= w.this_start) AS orders,
                COALESCE(SUM(total) FILTER (WHERE created_at >= w.this_start), 0)     AS revenue,
                COALESCE(SUM(total) FILTER (WHERE created_at >= w.prev_start
                                              AND created_at <  w.this_start), 0)     AS prev_revenue,
                MAX(currency)                                                         AS currency
              FROM attributed_orders, windows w
            )
            SELECT * FROM ev, ord
            """,
            {"days": days},
        ).fetchone()

    if row is None:
        return {}

    (impressions, clicks, adds, prev_impressions, prev_clicks, prev_adds,
     orders, revenue, prev_revenue, currency) = row

    return {
        "impressions": impressions,
        "clicks": clicks,
        "add_to_cart": adds,
        "orders": orders,
        "revenue": float(revenue),
        "currency": currency or "",
        "click_rate": round(clicks / impressions, 4) if impressions else None,
        # Wiser calls this "conversion rate" and computes it clicks-to-sales,
        # so ours is the same ratio and comparable at a glance.
        "conversion_rate": round(orders / clicks, 4) if clicks else None,
        "change": {
            "impressions": _change(impressions, prev_impressions),
            "clicks": _change(clicks, prev_clicks),
            "add_to_cart": _change(adds, prev_adds),
            "revenue": _change(revenue, prev_revenue),
        },
    }


def _change(now, before) -> float | None:
    """
    Percentage change against the previous window.

    None when there is nothing to compare against - a rise from zero is not
    "infinite growth", it is a first measurement, and showing it as a number
    invites someone to read meaning into it.
    """
    now, before = float(now or 0), float(before or 0)
    if before == 0:
        return None
    return round((now - before) / before, 4)


def daily(days: int) -> list[dict]:
    """
    One row per day: clicks and attributed revenue.

    Every day in the range is returned, including the empty ones. A chart that
    silently drops quiet days compresses time and makes a gap look like a dip.
    """
    with connection() as conn:
        rows = conn.execute(
            """
            WITH days AS (
              SELECT generate_series(
                date_trunc('day', now() - make_interval(days => %(days)s - 1)),
                date_trunc('day', now()),
                interval '1 day'
              ) AS day
            ),
            clicks AS (
              SELECT date_trunc('day', created_at) AS day, COUNT(*) AS n
                FROM events
               WHERE type = 'click'
               GROUP BY 1
            ),
            money AS (
              SELECT date_trunc('day', created_at) AS day, SUM(total) AS revenue
                FROM attributed_orders
               GROUP BY 1
            )
            SELECT to_char(d.day, 'YYYY-MM-DD'),
                   COALESCE(c.n, 0),
                   COALESCE(m.revenue, 0)
              FROM days d
              LEFT JOIN clicks c ON c.day = d.day
              LEFT JOIN money  m ON m.day = d.day
             ORDER BY d.day
            """,
            {"days": days},
        ).fetchall()

    return [
        {"day": day, "clicks": clicks, "revenue": float(revenue)}
        for day, clicks, revenue in rows
    ]
