import { useEffect, useState } from 'react'
import { PAGE_TEMPLATES } from '../lib/pageTemplates'
import PageTemplateCard from './PageTemplateCard'
import SetupPanel from './SetupPanel'
import { getConfig, saveConfig } from './api'
import TokenPrompt from '../auth/TokenPrompt'
import useBlockStatus from './useBlockStatus'

/*
 * The screen this console exists for: which blocks appear on which page.
 *
 * A failed load falls back to an empty config and says so. It fails loudly
 * rather than pretending to have loaded — a console that silently shows an
 * empty configuration is how someone concludes the storefront is broken.
 *
 * Saving needs the write token. Rather than bundling it (a VITE_ variable is
 * readable by anyone who opens the page), a 401 raises the prompt and the
 * attempted save is retried once the password is entered.
 */
export default function SetupWidgets() {
  const [config, setConfig] = useState(null)
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [needsToken, setNeedsToken] = useState(false)
  const [pending, setPending] = useState(null)
  const { byId: blockStatus, loaded: statusLoaded } = useBlockStatus()

  useEffect(() => {
    getConfig()
      .then((data) => setConfig(data.config))
      .catch((err) => {
        setError(err.message)
        setConfig({ version: 1, enabled: true, placements: {} })
      })
  }, [])

  // Kept separate from `apply` so the token prompt can retry the same document
  // rather than asking the user to place the block again.
  const save = (next) => {
    setSaving(true)
    return saveConfig(next)
      .then(() => setNeedsToken(false))
      .catch((err) => {
        if (err.status === 401) {
          setNeedsToken(true)
          setPending(next)
        } else {
          setError(err.message)
        }
      })
      .finally(() => setSaving(false))
  }

  const apply = (templateId, rows) => {
    const next = {
      ...config,
      placements: { ...config.placements, [templateId]: rows },
    }
    setConfig(next)
    setEditing(null)
    save(next)
  }

  // Blocks placed and enabled somewhere, whose list the pipeline has not
  // published. They render nothing on the storefront, and that should be
  // visible here rather than discovered there.
  const unpublished = statusLoaded
    ? [
        ...new Set(
          Object.values(config?.placements || {})
            .flat()
            .filter((row) => row.enabled)
            .map((row) => row.block)
            .filter((id) => blockStatus[id] && !blockStatus[id].list_published)
        ),
      ]
    : []

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
      {needsToken && (
        <TokenPrompt
          onSubmit={() => save(pending)}
          onCancel={() => setNeedsToken(false)}
        />
      )}
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

      {unpublished.length > 0 && (
        <div className="note" style={{ marginBottom: 18 }}>
          <h3>WARNING: placed, but nothing published yet</h3>
          <p>
            {unpublished.map((id) => blockStatus[id].label).join(', ')} —
            configured here, but the pipeline has not published a list. These
            blocks render nothing on the storefront until it does.
          </p>
        </div>
      )}

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
