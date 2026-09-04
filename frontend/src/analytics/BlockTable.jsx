// Revenue per 1,000 impressions is the column that actually ranks blocks
// against each other — a block with a high CTR that sells nothing is still
// taking up page space.
export default function BlockTable({ rows = [] }) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Block</th>
          <th>Page</th>
          <th className="num">Impressions</th>
          <th className="num">Clicks</th>
          <th className="num">CTR</th>
          <th className="num">Add to cart</th>
          <th className="num">Attributed orders</th>
          <th className="num">Attributed revenue</th>
          <th className="num">Rev / 1k impr.</th>
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 && (
          <tr>
            <td colSpan={9} style={{ color: '#7a7a8c' }}>
              No events yet.
            </td>
          </tr>
        )}
        {rows.map((r) => (
          <tr key={`${r.block}-${r.page_template}`}>
            <td>{r.block}</td>
            <td>{r.page_template}</td>
            <td className="num">{r.impressions}</td>
            <td className="num">{r.clicks}</td>
            <td className="num">{r.ctr}</td>
            <td className="num">{r.add_to_carts}</td>
            <td className="num">{r.attributed_orders}</td>
            <td className="num">{r.attributed_revenue}</td>
            <td className="num">{r.revenue_per_1k}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
