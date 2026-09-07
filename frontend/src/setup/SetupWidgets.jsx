import { useEffect, useState } from 'react'
import { PAGE_TEMPLATES } from '../lib/pageTemplates'
import PageTemplateCard from './PageTemplateCard'
import SetupPanel from './SetupPanel'
import { getConfig, saveConfig, undoConfig } from './api'
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
  const [loadError, setLoadError] = useState('')
  const [saveError, setSaveError] = useState(null)
  const [hasPrevious, setHasPrevious] = useState(false)
  const [saving, setSaving] = useState(false)
  const [needsToken, setNeedsToken] = useState(false)
  const [pending, setPending] = useState(null)
  const { byId: blockStatus, loaded: statusLoaded } = useBlockStatus()

  useEffect(() => {
    getConfig()
      .then((data) => {
        setConfig(data.config)
        setHasPrevious(data.has_previous)
      })
      .catch((err) => {
        setLoadError(err.message)
        setConfig({ version: 1, enabled: true, placements: {} })
      })
  }, [])

  // Kept separate from `apply` so the token prompt can retry the same document
  // rather than asking the user to place the block again.
  //
  // `revert` is the config as the shop last confirmed it. A save that fails
  // rolls back to it: a console showing a placement the shop does not have is
  // the same lie as a console showing an empty config it cannot read.
  const save = (next, revert) => {
    setSaving(true)
    setSaveError(null)
    return saveConfig(next)
      .then(() => {
        setNeedsToken(false)
        setPending(null)
      })
      .catch((err) => {
        if (err.status === 401) {
          // Not a failure yet — the prompt will retry this same document.
          setNeedsToken(true)
          setPending({ next, revert })
        } else {
          setConfig(revert)
          setSaveError(err)
        }
      })
      .finally(() => setSaving(false))
  }

  const apply = (templateId, rows) => {
    const revert = config
    const next = {
      ...config,
      placements: { ...config.placements, [templateId]: rows },
    }
    setConfig(next)
    setEditing(null)
    save(next, revert)
  }

  const cancelToken = () => {
    // Abandoning the password abandons the change. Leaving it on screen would
    // show a placement the shop never received.
    if (pending) setConfig(pending.revert)
    setNeedsToken(false)
    setPending(null)
  }

  const undo = () => {
    setSaving(true)
    setSaveError(null)
    undoConfig()
      .then((data) => {
        setConfig(data.config)
        setHasPrevious(false)
      })
      .catch((err) => {
        if (err.status === 401) setNeedsToken(true)
        else setSaveError(err)
      })
      .finally(() => setSaving(false))
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
          onSubmit={() => pending && save(pending.next, pending.revert)}
          onCancel={cancelToken}
        />
      )}
      {loadError && (
        <div className="note" style={{ marginBottom: 18, borderLeftColor: '#b85450' }}>
          <h3>Not connected to the backend</h3>
          <p>
            <code>{loadError}</code>
          </p>
          <p>
            Showing an empty configuration. This is the console layout, not the
            live storefront state — do not read it as "no blocks are placed".
          </p>
        </div>
      )}
      {saveError && (
        <div className="note" style={{ marginBottom: 18, borderLeftColor: '#b85450' }}>
          <h3>Not saved</h3>
          {/* 422 carries field-level errors. "slots must be between 2 and 12"
              is worth far more than "Request failed (422)". */}
          {saveError.errors?.length ? (
            <ul>
              {saveError.errors.map((e) => (
                <li key={e.path}>
                  <code>{e.path}</code> — {e.message}
                </li>
              ))}
            </ul>
          ) : (
            <p>
              <code>{saveError.message}</code>
            </p>
          )}
          <p>The console has been rolled back to what the shop actually holds.</p>
        </div>
      )}
      {saving && <p className="card__sub">Saving…</p>}

      {hasPrevious && !saving && (
        <p className="card__sub" style={{ marginBottom: 18 }}>
          <button type="button" onClick={undo}>
            Undo last change
          </button>{' '}
          Restores the configuration this one replaced. One step only.
        </p>
      )}

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
