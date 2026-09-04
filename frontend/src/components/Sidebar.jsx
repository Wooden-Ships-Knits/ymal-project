import { useState } from 'react'
import { NAV, NAV_MORE } from '../lib/nav'

// Mirrors the Wiser sidebar it replaces, including the "More" fold. Items we
// do not replace stay listed but greyed, so the web team can see they are gone
// deliberately rather than wonder where they went.
function Item({ entry, active, onSelect }) {
  const classes = [
    'sidebar__item',
    active === entry.id ? 'is-active' : '',
    entry.status === 'n/a' ? 'is-na' : '',
  ].join(' ')

  return (
    <button className={classes} onClick={() => onSelect(entry.id)} type="button">
      <span className="sidebar__icon" aria-hidden="true" />
      <span className="sidebar__label">{entry.label}</span>
    </button>
  )
}

export default function Sidebar({ active, onSelect }) {
  const [moreOpen, setMoreOpen] = useState(false)

  return (
    <nav className="sidebar" aria-label="Console sections">
      <div className="sidebar__brand">YMAL</div>

      {NAV.map((entry) => (
        <Item key={entry.id} entry={entry} active={active} onSelect={onSelect} />
      ))}

      <button
        className="sidebar__more"
        onClick={() => setMoreOpen((open) => !open)}
        type="button"
        aria-expanded={moreOpen}
      >
        More {moreOpen ? '⌃' : '⌄'}
      </button>

      {moreOpen &&
        NAV_MORE.map((entry) => (
          <Item key={entry.id} entry={entry} active={active} onSelect={onSelect} />
        ))}
    </nav>
  )
}
