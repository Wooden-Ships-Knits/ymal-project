/*
 * The period every number on a screen is about.
 *
 * Two ways to ask, and only one of them is in charge at a time: the presets are
 * rolling windows from this moment, a custom range is calendar days with both
 * ends included. Picking either clears the other, so the screen can never show
 * one while the controls say the other.
 */
export const RANGES = [7, 30, 90]

// Today in the browser's own date, as the pickers' upper bound. Tomorrow holds
// nothing and asking for it looks like a broken screen.
export const today = () => new Date().toISOString().slice(0, 10)

export default function RangePicker({ days, range, draft, onDays, onDraft, onApply, onClear }) {
  return (
    <div
      style={{ marginBottom: 14, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}
    >
      {RANGES.map((n) => (
        <button
          key={n}
          type="button"
          className="btn"
          onClick={() => onDays(n)}
          // Pressed only while a preset is what is actually being shown: with a
          // custom range applied, none of them is.
          aria-pressed={!range && n === days}
          style={{ fontWeight: !range && n === days ? 600 : 400 }}
        >
          Last {n} days
        </button>
      ))}

      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (draft.start && draft.end) onApply()
        }}
        style={{ display: 'flex', gap: 6, alignItems: 'center', marginLeft: 6 }}
      >
        <label htmlFor="range-start" className="card__sub">From</label>
        <input
          id="range-start"
          type="date"
          className="input"
          max={draft.end || today()}
          value={draft.start}
          onChange={(e) => onDraft({ ...draft, start: e.target.value })}
        />
        <label htmlFor="range-end" className="card__sub">to</label>
        <input
          id="range-end"
          type="date"
          className="input"
          min={draft.start || undefined}
          max={today()}
          value={draft.end}
          onChange={(e) => onDraft({ ...draft, end: e.target.value })}
        />
        {/* Disabled until both ends exist: the API refuses half a range, and a
            button that only ever errors is not a button. */}
        <button type="submit" className="btn" disabled={!draft.start || !draft.end}>
          Apply
        </button>
        {range && (
          <button type="button" className="btn" onClick={onClear}>
            Clear
          </button>
        )}
      </form>
    </div>
  )
}
