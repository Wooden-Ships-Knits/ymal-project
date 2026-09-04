import { useEffect, useState } from 'react'
import { PAGE_TEMPLATES } from '../lib/pageTemplates'
import PageTemplateCard from './PageTemplateCard'
import SetupPanel from './SetupPanel'
import { getConfig, saveConfig } from './api'

/*
 * The screen this console exists for: which blocks appear on which page.
 *
 * The backend endpoints do not exist yet, so a failed load falls back to an
 * empty config and says so. It fails loudly rather than pretending to have
 * loaded — a console that silently shows an empty configuration is how someone
 * concludes the storefront is broken.
 */
export default function SetupWidgets() {
  const [config, setConfig] = useState(null)
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getConfig()
      .then((data) => setConfig(data.config))
      .catch((err) => {
        setError(err.message)
        setConfig({ version: 1, enabled: true, placements: {} })
      })
  }, [])

  const apply = (templateId, rows) => {
    const next = {
      ...config,
      placements: { ...config.placements, [templateId]: rows },
    }
    setConfig(next)
    setEditing(null)
    setSaving(true)
    saveConfig(next)
      .catch((err) => setError(err.message))
      .finally(() => setSaving(false))
  }

  if (!config) return <p>Loading…</p>

  if (editing) {
    return (
      <SetupPanel
        template={editing}
        placements={config.placements?.[editing.id] || []}
        onChange={apply}
        onClose={() => setEditing(null)}
      />
    )
  }

  return (
    <>
      {error && (
        <div className="note" style={{ marginBottom: 18, borderLeftColor: '#b85450' }}>
          <h3>Not connected to the backend</h3>
          <p>
            <code>{error}</code>
          </p>
          <p>
            Showing an empty configuration. This is the console layout, not the
            live storefront state — do not read it as "no blocks are placed".
          </p>
        </div>
      )}
      {saving && <p className="card__sub">Saving…</p>}

      <div className="grid">
        {PAGE_TEMPLATES.map((template) => (
          <PageTemplateCard
            key={template.id}
            template={template}
            placements={config.placements?.[template.id] || []}
            onSetup={setEditing}
          />
        ))}
      </div>
    </>
  )
}
