import Placeholder from '../components/Placeholder'

/*
 * Deliberately last, not first.
 *
 * A dashboard summarises; there is nothing to summarise until blocks are live
 * and events are landing. Building it now would mean inventing numbers.
 */
export default function Dashboard() {
  return (
    <Placeholder heading="Nothing to summarise yet">
      <p>
        A dashboard is a summary of other screens, so it comes after them. Once
        blocks are live and events are landing, this is where the one-glance
        view goes: which blocks are placed where, what each earned this week,
        and whether the nightly build ran.
      </p>
      <p>
        Until then, <strong>Setup Widgets</strong> is the screen that does the
        work.
      </p>
    </Placeholder>
  )
}
