/*
 * Per-block performance.
 *
 * Click rate is clicks over impressions, both from the same window - a rate
 * built from two different periods is not a rate. A block with no impressions
 * shows a dash rather than 0%, because "not seen" and "seen and ignored" are
 * different things and only one of them is bad.
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

export default function BlockTable({ blocks, revenue }) {
  const byBlock = Object.fromEntries((revenue || []).map((r) => [r.block, r]))

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
        </tr>
      </thead>
      <tbody>
        {blocks.map((b) => {
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
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
