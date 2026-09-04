import { BLOCKS } from '../lib/blocks'
import Placeholder from '../components/Placeholder'

/*
 * Wiser splits "which blocks exist" from "where they go". Here the five blocks
 * are fixed and defined in the backend, so this screen is about their state:
 * what each one computes, when it last built, and how deep the list is.
 *
 * Placement is Setup Widgets. This is the health view.
 */
export default function Recommendations() {
  return (
    <>
      <Placeholder heading="Block health — not wired up yet">
        <p>
          Once <code>/api/blocks</code> exists this table shows each block's
          last build, list depth and whether it has been published to Shopify.
          A block configured on a page but never built renders nothing, and
          that should be visible here rather than discovered on the storefront.
        </p>
      </Placeholder>

      <div style={{ marginTop: 22 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Block</th>
              <th>What it computes</th>
              <th>Needs an anchor</th>
              <th className="num">Last built</th>
              <th className="num">Depth</th>
            </tr>
          </thead>
          <tbody>
            {BLOCKS.map((b) => (
              <tr key={b.id}>
                <td><strong>{b.label}</strong></td>
                <td>{b.description}</td>
                <td>{b.requiresAnchor ? 'yes' : 'no'}</td>
                <td className="num">—</td>
                <td className="num">—</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
