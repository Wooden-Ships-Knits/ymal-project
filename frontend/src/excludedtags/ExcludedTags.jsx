import { useEffect, useMemo, useState } from 'react'
import { getExcludedTags, saveExcludedTags } from './api'
import { startRun } from '../run/api'
import TokenPrompt from '../auth/TokenPrompt'

/*
 * Exclude by Tag — products the store still sells, but that Top Selling (MYNTS)
 * and Trending should stop recommending.
 *
 * Made for occasions: Halloween sweaters keep selling right up to the shipping
 * cutoff, so a 14-day sales list still puts them first when it is too late to
 * deliver. The products stay live and buyable; they only drop out of those
 * two lists, and the next best sellers move up.
 *
 * A WHOLE tag matches, ignoring case - "halloween" does not also catch
 * "halloween gift", so the count beside each tag is there to check that what
 * is listed catches what was meant.
 *
 * Applied when the lists are built: nightly, or now with Rebuild. The SOP is
 * docs/sop-excluded-tags.md.
 */

const clean = (tag) => tag.split(/\s+/).filter(Boolean).join(' ').toLowerCase()

export default function ExcludedTags() {
  const [meta, setMeta] = useState(null)
  const [draft, setDraft] = useState([])
  const [entry, setEntry] = useState('')
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState([])
  const [needsToken, setNeedsToken] = useState(false)
  const [pendingWrite, setPendingWrite] = useState(null)
  const [saved, setSaved] = useState('')
  const [running, setRunning] = useState(false)

  useEffect(() => {
    getExcludedTags()
      .then((data) => {
        setMeta(data)
        setDraft(data.tags)
      })
      .catch((err) => setError(err.message))
  }, [])

  const known = useMemo(() => new Set(meta?.known_tags || []), [meta])

  const dirty = useMemo(
    () => meta && JSON.stringify(draft) !== JSON.stringify(meta.tags),
    [draft, meta],
  )

  const add = (event) => {
    event.preventDefault()
    const tag = clean(entry)
    if (tag && !draft.includes(tag)) setDraft((d) => [...d, tag])
    setEntry('')
  }

  const remove = (tag) => setDraft((d) => d.filter((t) => t !== tag))

  const runWrite = (fn) => {
    setError('')
    setSaved('')
    setPendingWrite(() => fn)
    fn()
      .then((next) => {
        setNeedsToken(false)
        setPendingWrite(null)
        setFieldErrors([])
        if (next?.tags) {
          setMeta((m) => ({ ...m, tags: next.tags, counts: next.counts }))
          setDraft(next.tags)
        }
        setSaved(next?.updated_at ? `Saved ${new Date(next.updated_at).toLocaleString()}` : 'Started')
      })
      .catch((err) => {
        if (err.status === 401) setNeedsToken(true)
        else {
          setFieldErrors(err.errors || [])
          setError(err.errors?.length ? '' : err.message)
        }
      })
  }

  const save = () => runWrite(() => saveExcludedTags(draft))

  const rebuild = () => {
    setRunning(true)
    runWrite(() => startRun(false).finally(() => setRunning(false)))
  }

  if (error && !meta) return <p className="note">{error}</p>
  if (!meta) return <p>Loading…</p>

  return (
    <>
      {needsToken && (
        <TokenPrompt
          onSubmit={() => pendingWrite && runWrite(pendingWrite)}
          onCancel={() => setNeedsToken(false)}
        />
      )}

      <div className="note" style={{ marginBottom: 18 }}>
        <h3>What this changes</h3>
        <p>
          Products with any of these Shopify tags are left out of{' '}
          <strong>Top Selling (MYNTS)</strong> and <strong>Trending</strong>.
          They stay live and buyable everywhere else; the next best sellers take
          their place.
        </p>
        <p>
          A whole tag matches, ignoring capitals — <code>halloween</code> does
          not also catch <code>halloween gift</code>, so add each tag you mean.
          It applies at the next nightly run (20:00 Makassar), or now with{' '}
          <strong>Rebuild and publish</strong>.
        </p>
      </div>

      {error && <p className="note">{error}</p>}
      {fieldErrors.length > 0 && (
        <div className="note" style={{ marginBottom: 18 }}>
          {fieldErrors.map((e) => (
            <div key={e.path}>
              <strong>{e.path}</strong> {e.message}
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ maxWidth: 720 }}>
        <div className="card__title">Excluded tags</div>

        <form onSubmit={add} style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <input
            className="input"
            list="ymal-known-tags"
            placeholder="Type or pick a tag, e.g. halloween"
            value={entry}
            onChange={(e) => setEntry(e.target.value)}
            style={{ flex: 1 }}
          />
          <datalist id="ymal-known-tags">
            {meta.known_tags.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
          <button className="btn" type="submit" disabled={!clean(entry)}>
            Add
          </button>
        </form>

        <table className="table">
          <tbody>
            {draft.map((tag) => {
              const count = meta.counts?.[tag]
              return (
                <tr key={tag}>
                  <td>
                    {tag}
                    <div className="card__sub">
                      {count != null
                        ? `${count} active product${count === 1 ? '' : 's'}`
                        : 'Save to see how many products it catches'}
                      {known.size > 0 && !known.has(tag) && ' — no product has this exact tag'}
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn" onClick={() => remove(tag)}>
                      Remove
                    </button>
                  </td>
                </tr>
              )
            })}
            {!draft.length && (
              <tr>
                <td className="card__sub">No tags. Top Selling and Trending show every eligible product.</td>
              </tr>
            )}
          </tbody>
        </table>

        <div className="card__foot" style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          <button className="btn btn--primary" onClick={save} disabled={!dirty}>
            Save
          </button>
          <button className="btn" onClick={rebuild} disabled={running || dirty}>
            {running ? 'Rebuilding…' : 'Rebuild and publish'}
          </button>
        </div>
        {saved && <div className="card__sub">{saved}</div>}
        {dirty && <div className="card__sub">Unsaved — Rebuild uses the saved list.</div>}
      </div>
    </>
  )
}
