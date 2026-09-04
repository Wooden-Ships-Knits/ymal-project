import { useState } from 'react'
import { BLOCKS } from '../lib/blocks'
import { blockAllowedOn } from '../lib/pageTemplates'

/*
 * The editor behind a page template's Setup button.
 *
 * Everything it produces is one entry in `placements[template]` — which block,
 * in what order, how many slots, what heading, on or off. Nothing else.
 *
 * Blocks that cannot work on this template are shown disabled with the reason,
 * rather than hidden: "why can't I put Featured on the homepage" should be
 * answered on the screen, not in a document.
 */
export default function SetupPanel({ template, placements, onChange, onClose }) {
  const [rows, setRows] = useState(placements)

  const update = (id, patch) =>
    setRows((current) =>
      current.map((r) => (r.block === id ? { ...r, ...patch } : r)),
    )

  const toggle = (block) => {
    setRows((current) => {
      const existing = current.find((r) => r.block === block.id)
      if (existing) return current.filter((r) => r.block !== block.id)
      return [
        ...current,
        {
          block: block.id,
          heading: block.defaultHeading,
          slots: block.defaultSlots,
          enabled: true,
        },
      ]
    })
  }

  const move = (index, delta) => {
    setRows((current) => {
      const next = [...current]
      const target = index + delta
      if (target < 0 || target >= next.length) return current
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  return (
    <div className="note" style={{ maxWidth: 820 }}>
      <h3>{template.label} — blocks</h3>
      <p>Order here is the order on the page.</p>

      <table className="table">
        <thead>
          <tr>
            <th>Block</th>
            <th>Heading</th>
            <th className="num">Slots</th>
            <th className="num">Order</th>
            <th className="num">On</th>
          </tr>
        </thead>
        <tbody>
          {BLOCKS.map((block) => {
            const allowed = blockAllowedOn(block, template)
            const row = rows.find((r) => r.block === block.id)
            const index = rows.findIndex((r) => r.block === block.id)

            return (
              <tr key={block.id} style={{ opacity: allowed ? 1 : 0.45 }}>
                <td>
                  <strong>{block.label}</strong>
                  <div className="card__sub" style={{ margin: 0 }}>
                    {allowed
                      ? block.description
                      : 'Needs a product to be about — this page has no anchor.'}
                  </div>
                </td>
                <td>
                  <input
                    className="btn"
                    style={{ width: 190 }}
                    value={row?.heading ?? block.defaultHeading}
                    disabled={!row || !allowed}
                    onChange={(e) => update(block.id, { heading: e.target.value })}
                  />
                </td>
                <td className="num">
                  <input
                    className="btn"
                    style={{ width: 64, textAlign: 'right' }}
                    type="number"
                    min={2}
                    max={12}
                    value={row?.slots ?? block.defaultSlots}
                    disabled={!row || !allowed}
                    onChange={(e) =>
                      update(block.id, { slots: Number(e.target.value) })
                    }
                  />
                </td>
                <td className="num">
                  <button className="btn" type="button" disabled={!row || index <= 0}
                          onClick={() => move(index, -1)}>↑</button>{' '}
                  <button className="btn" type="button"
                          disabled={!row || index < 0 || index >= rows.length - 1}
                          onClick={() => move(index, 1)}>↓</button>
                </td>
                <td className="num">
                  <input
                    type="checkbox"
                    checked={Boolean(row)}
                    disabled={!allowed}
                    onChange={() => toggle(block)}
                  />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn btn--primary" type="button"
                onClick={() => onChange(template.id, rows)}>
          Save
        </button>
        <button className="btn" type="button" onClick={onClose}>Cancel</button>
      </div>

      <p style={{ marginTop: 14 }}>
        Save writes <code>ymal.config</code> and nothing else. The previous
        version is kept, so an undo is one click.
      </p>
    </div>
  )
}
