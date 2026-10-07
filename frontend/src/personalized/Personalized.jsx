import { useEffect, useMemo, useState } from 'react'
import { getPersonalized, savePersonalized } from './api'
import TokenPrompt from '../auth/TokenPrompt'

/*
 * Personalized Products — titles whose cards must send the shopper to the
 * product page instead of adding straight to the cart.
 *
 * Textify asks for the name or number on the product page and nowhere else.
 * The quick Add on Recently Viewed in the cart drawer, and on the cart popup,
 * skipped it, and orders arrived with no name and no number.
 *
 * Titles, not products, because Textify matches by title ("Product title |
 * Equals") and one title covers every colorway. Keep this list the same as
 * Textify's.
 *
 * Unlike Ranking there is no Rebuild: the theme reads the saved list on every
 * page, so Save is live.
 */

// Textify's fields as of 2026-10-07. Offered once, while nothing is saved, so
// the first save does not depend on retyping them from the Textify screen.
const FROM_TEXTIFY = [
  'MONOGRAM CREW CHUNKY',
  'CUSTOM JERSEY 3 NUMBER LIGHTWEIGHT',
  'CUSTOMIZABLE NUMBER JERSEY LIGHTWEIGHT',
  'CUSTOMIZABLE NUMBER JERSEY COTTON',
  'PERSONALIZED NUMBER JERSEY LIGHTWEIGHT',
]

const clean = (title) => title.split(/\s+/).filter(Boolean).join(' ').toUpperCase()

export default function Personalized() {
  const [meta, setMeta] = useState(null)
  const [draft, setDraft] = useState([])
  const [entry, setEntry] = useState('')
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState([])
  const [needsToken, setNeedsToken] = useState(false)
  const [saved, setSaved] = useState('')

  useEffect(() => {
    getPersonalized()
      .then((data) => {
        setMeta(data)
        setDraft(data.titles.length ? data.titles : FROM_TEXTIFY)
      })
      .catch((err) => setError(err.message))
  }, [])

  const known = useMemo(() => new Set(meta?.known_titles || []), [meta])

  const dirty = useMemo(
    () => meta && JSON.stringify(draft) !== JSON.stringify(meta.titles),
    [draft, meta],
  )

  const add = (event) => {
    event.preventDefault()
    const title = clean(entry)
    if (title && !draft.includes(title)) setDraft((d) => [...d, title])
    setEntry('')
  }

  const remove = (title) => setDraft((d) => d.filter((t) => t !== title))

  const save = () => {
    setError('')
    setSaved('')
    savePersonalized(draft)
      .then((next) => {
        setNeedsToken(false)
        setFieldErrors([])
        setMeta((m) => ({ ...m, titles: next.titles }))
        setDraft(next.titles)
        setSaved(next.updated_at ? `Saved ${new Date(next.updated_at).toLocaleString()}` : 'Saved')
      })
      .catch((err) => {
        if (err.status === 401) setNeedsToken(true)
        else {
          setFieldErrors(err.errors || [])
          setError(err.errors?.length ? '' : err.message)
        }
      })
  }

  if (error && !meta) return <p className="note">{error}</p>
  if (!meta) return <p>Loading…</p>

  return (
    <>
      {needsToken && <TokenPrompt onSubmit={save} onCancel={() => setNeedsToken(false)} />}

      <div className="note" style={{ marginBottom: 18 }}>
        <h3>What this changes</h3>
        <p>
          Products with these titles lose the quick <strong>Add</strong> button
          in YMAL&apos;s Recently Viewed (cart drawer) and the cart popup. They
          show a <strong>Personalize</strong> link to the product page instead,
          where Textify asks for the name or number.
        </p>
        <p>
          Keep it the same as the product titles in Textify. Live as soon as you
          save — no rebuild needed.
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
        <div className="card__title">Personalized product titles</div>
        {!meta.titles.length && (
          <div className="card__sub" style={{ marginBottom: 10 }}>
            Nothing saved yet. Pre-filled from Textify — check and Save.
          </div>
        )}

        <form onSubmit={add} style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <input
            className="input"
            list="ymal-known-titles"
            placeholder="Type or pick a product title"
            value={entry}
            onChange={(e) => setEntry(e.target.value)}
            style={{ flex: 1 }}
          />
          <datalist id="ymal-known-titles">
            {meta.known_titles.map((t) => (
              <option key={t} value={t} />
            ))}
          </datalist>
          <button className="btn" type="submit" disabled={!clean(entry)}>
            Add
          </button>
        </form>

        <table className="table">
          <tbody>
            {draft.map((title) => (
              <tr key={title}>
                <td>
                  {title}
                  {known.size > 0 && !known.has(title) && (
                    <div className="card__sub">
                      No active product has this exact title — check the spelling.
                    </div>
                  )}
                </td>
                <td style={{ textAlign: 'right' }}>
                  <button className="btn" onClick={() => remove(title)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {!draft.length && (
              <tr>
                <td className="card__sub">No titles. Every card keeps its Add button.</td>
              </tr>
            )}
          </tbody>
        </table>

        <div className="card__foot" style={{ display: 'flex', gap: 8, marginTop: 14 }}>
          <button className="btn btn--primary" onClick={save} disabled={!dirty}>
            Save
          </button>
        </div>
        {saved && <div className="card__sub">{saved}</div>}
        {dirty && <div className="card__sub">Unsaved.</div>}
      </div>
    </>
  )
}
