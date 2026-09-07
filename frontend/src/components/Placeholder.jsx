/*
 * An honest empty screen.
 *
 * Every unbuilt tab renders this rather than a fake chart or a dummy table.
 * A mock that looks real is worse than an empty one: someone eventually
 * reports the numbers to a meeting.
 */
export default function Placeholder({ heading, children }) {
  return (
    <div className="note">
      <h3>{heading}</h3>
      {children}
    </div>
  )
}
