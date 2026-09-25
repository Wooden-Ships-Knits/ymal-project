/*
 * Per-block performance.
 *
 * Click rate is clicks over impressions, both from the same window - a rate
 * built from two different periods is not a rate. A block with no impressions
 * shows a dash rather than 0%, because "not seen" and "seen and ignored" are
 * different things and only one of them is bad.
 *
 * TWO REVENUE COLUMNS. "Revenue" is the whole value of every order that
 * involved the block, which is the convention upsell apps report and is
 * generous: a shopper can click a recommendation, buy something else entirely,
 * and the order still counts here. "Direct" is only the recommended product
 * itself, in the orders that actually contained it. The gap between them is
 * the part nobody should quietly claim credit for.
 */
function percent(value) {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

function money(value, currency) {
  if (!value) return '—'
  return `${currency || ''} ${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`.trim()
}

const ALL_BLOCKS = [
  'featured',
  'trending',
  'top_selling',
  'new_arrivals',
  'recently_viewed',
  // Hardcoded, so a block missing here records events that never appear in the
  // table - silent in the same way a block missing from the API allowlist is.
  'inspired_by_views',
  'cart_popup',
]

export default function BlockTable({ blocks, revenue }) {
  const byBlock = Object.fromEntries((revenue || []).map((r) => [r.block, r]))
  const measured = Object.fromEntries((blocks || []).map((b) => [b.block, b]))

  // Every block is listed whether or not it has been seen, so the report has
  // its full shape from the first day and a block with no traffic is visibly
  // absent rather than silently missing from the table.
  const rows = ALL_BLOCKS.map(
    (id) =>
      measured[id] || {
        block: id,
        impressions: 0,
        clicks: 0,
        add_to_cart: 0,
        click_rate: null,
        add_rate: null,
      }
  )

  return (
    <table className="table">
      <thead>
        <tr>
          <th>Block</th>
          <th style={{ textAlign: 'right' }}>Seen</th>
          <th style={{ textAlign: 'right' }}>Clicks</th>
          <th style={{ textAlign: 'right' }}>Click rate</th>
          <th style={{ textAlign: 'right' }}>Added to cart</th>
          <th style={{ textAlign: 'right' }}>Orders</th>
          <th style={{ textAlign: 'right' }}>Revenue</th>
          <th style={{ textAlign: 'right' }}>Direct</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((b) => {
          const money_ = byBlock[b.block] || {}
          return (
            <tr key={b.block}>
              <td>{b.block.replace(/_/g, ' ')}</td>
              <td style={{ textAlign: 'right' }}>{b.impressions.toLocaleString()}</td>
              <td style={{ textAlign: 'right' }}>{b.clicks.toLocaleString()}</td>
              <td style={{ textAlign: 'right' }}>{percent(b.click_rate)}</td>
              <td style={{ textAlign: 'right' }}>{b.add_to_cart.toLocaleString()}</td>
              <td style={{ textAlign: 'right' }}>{money_.orders || '—'}</td>
              <td style={{ textAlign: 'right' }}>
                {money(money_.revenue, money_.currency)}
              </td>
              <td style={{ textAlign: 'right' }}>
                {money(money_.direct_revenue, money_.currency)}
                {money_.direct_orders ? (
                  <span className="card__sub"> ({money_.direct_orders})</span>
                ) : null}
              </td>
            </tr>
          )
        })}
      </tbody>
      <caption
        style={{ captionSide: 'bottom', textAlign: 'left', paddingTop: 10 }}
        className="card__sub"
      >
        Revenue is the whole value of every order that involved the block, even
        when the shopper bought something else. Direct counts only the
        recommended product itself, in the orders that contained it, with the
        number of such orders in brackets.
      </caption>
    </table>
  )
}
