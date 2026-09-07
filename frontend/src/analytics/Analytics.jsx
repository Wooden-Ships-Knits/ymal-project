import Placeholder from '../components/Placeholder'
import BlockTable from './BlockTable'

/*
 * Per-block performance — the screen that answers "is this block worth the
 * page space".
 *
 * The table is real; the data behind it is not, because the event endpoint and
 * its store do not exist yet. It renders empty rather than with sample numbers
 * on purpose: a mock that looks real ends up quoted in a meeting.
 */
export default function Analytics() {
  return (
    <>
      <Placeholder heading="No event data yet">
        <p>
          This screen needs three things that are not built: the storefront
          events (<code>ymal_impression</code>, <code>ymal_click</code>,{' '}
          <code>ymal_atc</code>), an endpoint to receive them, and the Postgres
          table behind it.
        </p>
        <p>
          <strong>Attribution is not incrementality.</strong> Matching a click
          to an order measures what a block touched, not what it caused. The
          honest number needs a holdout — roughly 10% of sessions seeing no
          blocks — and it cannot be applied retroactively, so it has to be
          switched on with the first block that ships.
        </p>
      </Placeholder>

      <div style={{ marginTop: 22 }}>
        <BlockTable rows={[]} />
      </div>
    </>
  )
}
