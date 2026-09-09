/*
 * The headline numbers, with which way each is moving.
 *
 * The comparison is against the immediately preceding window of the same
 * length - last 30 days against the 30 before - which is the only comparison
 * that keeps its meaning as time passes.
 *
 * A change of null is drawn as nothing rather than as a number. A rise from
 * zero is not growth, it is a first measurement, and showing "+100%" invites
 * someone to read a trend into a single data point.
 */
function Delta({ value }) {
  if (value == null) return <span className="tile__delta is-flat">no prior period</span>
  if (value === 0) return <span className="tile__delta is-flat">no change</span>

  const up = value > 0
  return (
    <span className={`tile__delta ${up ? 'is-up' : 'is-down'}`}>
      {/* An arrow as well as the colour, so this is not colour-alone. */}
      {up ? '▲' : '▼'} {Math.abs(value * 100).toFixed(1)}%
    </span>
  )
}

function Tile({ label, value, sub, change }) {
  return (
    <div className="tile">
      <div className="tile__label">{label}</div>
      <div className="tile__value">{value}</div>
      <div className="tile__foot">
        {sub && <span className="tile__sub">{sub}</span>}
        <Delta value={change} />
      </div>
    </div>
  )
}

export default function StatTiles({ totals }) {
  const t = totals || {}
  const money = (v) =>
    `${t.currency || ''} ${(v || 0).toLocaleString(undefined, {
      maximumFractionDigits: 0,
    })}`.trim()
  const percent = (v) => (v == null ? '—' : `${(v * 100).toFixed(2)}%`)

  return (
    <div className="tiles">
      <Tile
        label="Attributed sales"
        value={money(t.revenue)}
        sub={`${(t.orders || 0).toLocaleString()} orders`}
        change={t.change?.revenue}
      />
      <Tile
        label="Clicks"
        value={(t.clicks || 0).toLocaleString()}
        sub={`${(t.impressions || 0).toLocaleString()} seen`}
        change={t.change?.clicks}
      />
      <Tile
        label="Added to cart"
        value={(t.add_to_cart || 0).toLocaleString()}
        change={t.change?.add_to_cart}
      />
      <Tile
        label="Conversion rate"
        value={percent(t.conversion_rate)}
        sub="clicks to orders"
      />
    </div>
  )
}
