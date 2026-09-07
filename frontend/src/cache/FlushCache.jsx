import Placeholder from '../components/Placeholder'

/*
 * Wiser's "Flush Cache" maps onto something we genuinely need: rebuild the
 * block lists now, rather than waiting for tonight's run.
 *
 * The web team will want it after a product launch or a price change, and
 * "wait until tomorrow" is not an answer they should have to accept.
 */
export default function FlushCache() {
  return (
    <Placeholder heading="Rebuild now — not wired up yet">
      <p>
        The blocks rebuild nightly. This screen triggers a rebuild on demand,
        for the times that is too slow: a launch went live this morning, a
        product was pulled, prices moved.
      </p>
      <p>
        It runs the same code as the scheduled job —{' '}
        <code>python -m scripts.build_blocks</code> — then publishes. It should
        show what changed, not just report success: which lists moved and by how
        much, so an unexpected rebuild is visible rather than silent.
      </p>
      <p>
        Needs a guard against being pressed repeatedly. The order pull is
        thousands of orders; the sibling PPA console solves this with a
        single-run lock.
      </p>
    </Placeholder>
  )
}
