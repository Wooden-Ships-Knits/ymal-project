import { useEffect, useState } from 'react'
import { getAnalytics, getTrackingHealth } from './api'
import BlockTable from './BlockTable'
import StatTiles from './StatTiles'
import TrendChart from './TrendChart'

/*
 * How each block is actually performing.
 *
 * Reads what the storefront beacon recorded. Empty until the tracking script
 * is on the theme - and it says so rather than showing zeroes, because a table
 * of zeroes reads as "nothing works" when the truth is "nothing is measured
 * yet".
 */
const RANGES = [7, 30, 90]

export default function Analytics() {
  const [days, setDays] = useState(30)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  // Checked once per visit, not per range change - it probes the network.
  const [health, setHealth] = useState(null)

  useEffect(() => {
    getTrackingHealth()
      .then(setHealth)
      // A failing health check must not replace the screen. The worst case is
      // that we cannot say why the numbers are zero, which is where we were
      // before this existed.
      .catch(() => setHealth(null))
  }, [])

  useEffect(() => {
    setError('')
    setData(null)
    getAnalytics(days)
      .then(setData)
      .catch((err) => setError(err.message))
  }, [days])

  if (error) {
    return (
      <div className="note" style={{ borderLeftColor: '#b85450' }}>
        <h3>Analytics unavailable</h3>
        <p>
          <code>{error}</code>
        </p>
        <p>
          A 503 here means tracking storage is not configured - the API needs
          the database, which docker compose starts alongside it.
        </p>
      </div>
    )
  }

  if (!data) return <p>Loading…</p>

  // The layout is always drawn, even with nothing in it. An empty state that
  // replaces the whole screen hides the thing you need to look at while
  // setting it up, and the banner below says plainly why every number is zero.
  const nothingYet = data.blocks.length === 0

  return (
    <>
      <p style={{ marginBottom: 18 }}>
        {RANGES.map((n) => (
          <button
            key={n}
            type="button"
            className="btn"
            onClick={() => setDays(n)}
            aria-pressed={n === days}
            style={{
              marginRight: 8,
              fontWeight: n === days ? 600 : 400,
            }}
          >
            Last {n} days
          </button>
        ))}
      </p>

      {/*
        Two different zeroes. "Nobody has clicked yet" is fine and expected;
        "the endpoint refuses every beacon" is a broken deployment that looked
        exactly the same until this check existed. Say which one it is.
      */}
      {health && !health.ok && (
        <div className="note" style={{ marginBottom: 18, borderLeftColor: '#b85450' }}>
          <h3>Tracking is not recording</h3>
          <p>{health.hint}</p>
          <p className="card__sub">
            Probed <code>{health.url}</code> as a shopper's browser would
            {health.status ? ` — HTTP ${health.status}` : ' — no answer'}.
            {health.detail ? ` ${health.detail}` : ''}
          </p>
        </div>
      )}

      {nothingYet && (!health || health.ok) && (
        <div className="note" style={{ marginBottom: 18 }}>
          <h3>Nothing tracked yet</h3>
          <p>
            Every number below is zero because no events have been recorded.
            That is expected until <code>assets/ymal-track.js</code> is on the
            theme and a shopper has seen a YMAL block.
            {health?.ok && ' The endpoint itself is reachable and working.'}
          </p>
          <p>
            This data cannot be collected retroactively, so the sooner the
            script is installed, the sooner there is something to read here.
          </p>
        </div>
      )}

      <StatTiles totals={data.totals} />
      <TrendChart daily={data.daily || []} currency={data.totals?.currency} />
      <BlockTable blocks={data.blocks} revenue={data.revenue} />
    </>
  )
}
