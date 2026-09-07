import BlockChip from '../components/BlockChip'
import { blockById } from '../lib/blocks'

// One card per page template — the grid that is the whole point of this
// console. Shows what is placed there and opens the editor.
export default function PageTemplateCard({ template, placements = [], onSetup }) {
  const active = placements.filter((p) => p.enabled !== false)

  return (
    <section className="card">
      <h2 className="card__title">{template.label}</h2>
      <p className="card__sub">
        {template.v1 ? 'ships in v1' : 'later'}
        {template.anchor ? ' · has an anchor product' : ''}
      </p>

      <div className="card__chips">
        {placements.length === 0 && (
          <span className="chip is-off">No blocks placed</span>
        )}
        {placements.map((p) => {
          const block = blockById(p.block)
          if (!block) return null
          return (
            <BlockChip
              key={p.block}
              block={block}
              enabled={p.enabled !== false}
              slots={p.slots}
            />
          )
        })}
      </div>

      <div className="card__foot">
        <button className="btn" type="button" onClick={() => onSetup(template)}>
          Setup
        </button>
        {active.length > 0 && (
          <span className="card__sub" style={{ marginLeft: 12 }}>
            {active.length} block{active.length === 1 ? '' : 's'} live
          </span>
        )}
      </div>
    </section>
  )
}
