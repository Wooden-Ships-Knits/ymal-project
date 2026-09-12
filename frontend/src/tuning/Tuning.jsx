import { useEffect, useMemo, useRef, useState } from 'react'
import { getProducts, getTuning, previewTuning, resetTuning, saveTuning } from './api'
import { startRun } from '../run/api'
import TokenPrompt from '../auth/TokenPrompt'

/*
 * Ranking — the knobs that decide the ORDER of a recommendation row.
 *
 * The preview is the point of this screen. Before it existed, trying a weight
 * meant editing settings.py, running the pipeline for three minutes,
 * publishing to Shopify and looking at the storefront — so nobody tried more
 * than twice. Here a slider moves and the ranking below re-sorts, against the
 * real catalog, without saving or publishing anything.
 *
 * Saving and publishing are deliberately two separate actions. Save stores the
 * numbers; Rebuild runs the pipeline and writes to the live shop. Tying them
 * together would mean fiddling with a slider fired off three Shopify
 * republishes.
 */

// Long enough that dragging a slider does not fire a request per pixel, short
// enough to feel live.
const DEBOUNCE_MS = 250

const FACET_HELP = {
  motif: 'What is pictured or knitted — pumpkin, ghost, stripe, fair isle.',
  fabric: 'Chunky, cotton, wool blend, lightweight.',
  colour: 'Weak on this catalog: nearly everything is a neutral.',
  silhouette: 'Crew with crew, v-neck with v-neck. From product type, not tags.',
  collection: "The merchandiser's own grouping.",
  other: 'Occasion and theme tags — halloween, gameday, and the release drop.',
}

function Slider({ label, help, value, min, max, step, onChange }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
        <label style={{ fontWeight: 600 }}>{label}</label>
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: '100%' }}
      />
      {help && <div className="card__sub">{help}</div>}
    </div>
  )
}

export default function Tuning() {
  const [meta, setMeta] = useState(null)
  const [draft, setDraft] = useState(null)
  const [products, setProducts] = useState([])
  const [anchor, setAnchor] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState([])
  const [needsToken, setNeedsToken] = useState(false)
  const [pendingWrite, setPendingWrite] = useState(null)
  const [saved, setSaved] = useState('')
  const [running, setRunning] = useState(false)
  const debounce = useRef(null)

  useEffect(() => {
    Promise.all([getTuning(), getProducts()])
      .then(([tuning, styles]) => {
        setMeta(tuning)
        setDraft(tuning.effective)
        setProducts(styles)
        if (styles.length) setAnchor(styles[0].product_id)
      })
      .catch((err) => setError(err.message))
  }, [])

  // Re-rank whenever the draft or the chosen product changes.
  useEffect(() => {
    if (!draft || !anchor) return
    clearTimeout(debounce.current)
    debounce.current = setTimeout(() => {
      previewTuning(anchor, draft)
        .then((next) => {
          setResult(next)
          setFieldErrors([])
        })
        .catch((err) => {
          setFieldErrors(err.errors || [])
          setError(err.errors?.length ? '' : err.message)
        })
    }, DEBOUNCE_MS)
    return () => clearTimeout(debounce.current)
  }, [draft, anchor])

  const dirty = useMemo(
    () => meta && JSON.stringify(draft) !== JSON.stringify(meta.effective),
    [draft, meta],
  )

  const atDefaults = useMemo(
    () => meta && JSON.stringify(draft) === JSON.stringify(meta.defaults),
    [draft, meta],
  )

  const setWeight = (facet, value) =>
    setDraft((d) => ({ ...d, weights: { ...d.weights, [facet]: value } }))

  const runWrite = (fn) => {
    setError('')
    setSaved('')
    setPendingWrite(() => fn)
    fn()
      .then((next) => {
        setNeedsToken(false)
        setPendingWrite(null)
        if (next?.effective) {
          setMeta((m) => ({ ...m, saved: next.tuning, effective: next.effective }))
          setDraft(next.effective)
        }
        setSaved(next?.updated_at ? `Saved ${new Date(next.updated_at).toLocaleString()}` : 'Saved')
      })
      .catch((err) => {
        if (err.status === 401) setNeedsToken(true)
        else {
          setFieldErrors(err.errors || [])
          setError(err.errors?.length ? '' : err.message)
        }
      })
  }

  const save = () => runWrite(() => saveTuning(draft))

  // Sends null rather than a copy of today's defaults, so a later change to
  // settings.py is not overridden by numbers nobody chose.
  const reset = () => runWrite(() => resetTuning())

  const rebuild = () => {
    setRunning(true)
    runWrite(() => startRun(false).finally(() => setRunning(false)))
  }

  if (error && !meta) return <p className="note">{error}</p>
  if (!meta || !draft) return <p>Loading…</p>

  const limits = meta.limits

  return (
    <>
      {needsToken && (
        <TokenPrompt
          onSubmit={() => pendingWrite && runWrite(pendingWrite)}
          onCancel={() => setNeedsToken(false)}
        />
      )}

      <div className="note" style={{ marginBottom: 18 }}>
        <h3>What these change</h3>
        <p>
          The <strong>order</strong> of a recommendation row, and nothing else.
          They cannot make a sold-out, markdown or fixed-stock product appear —
          eligibility and the season rule stay in the code, because a wrong
          value there puts the wrong product in front of a shopper rather than
          just an oddly-sorted row.
        </p>
        <p>
          Nothing reaches the storefront until you <strong>Rebuild</strong>.
          Saving only stores the numbers; the nightly run would pick them up
          anyway at 20:00 Makassar.
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

      <div className="grid" style={{ gridTemplateColumns: 'minmax(280px, 360px) 1fr', gap: 24 }}>
        <div className="card">
          <div className="card__title">Ranking weights</div>

          <Slider
            label="Sales volume"
            help="How much the pool's best seller may rise. It only reorders — a product that is not similar enough to be in the pool never gets in by selling well."
            value={draft.popularity_weight}
            min={limits.popularity_weight[0]}
            max={limits.popularity_weight[1]}
            step={0.05}
            onChange={(v) => setDraft((d) => ({ ...d, popularity_weight: v }))}
          />

          <Slider
            label="Rare tag sharpness"
            help="1.0 is plain IDF. Higher makes a distinctive tag count for disproportionately more than a generic one; lower broadens pools towards whatever is generically similar."
            value={draft.idf_power}
            min={limits.idf_power[0]}
            max={limits.idf_power[1]}
            step={0.1}
            onChange={(v) => setDraft((d) => ({ ...d, idf_power: v }))}
          />

          <div className="card__title" style={{ marginTop: 22 }}>
            Tag facets
          </div>
          <div className="card__sub" style={{ marginBottom: 12 }}>
            Relative to each other. Scaling all six by the same amount changes
            nothing, because sales multiplies the total.
          </div>

          {meta.facets.map((facet) => (
            <Slider
              key={facet}
              label={facet}
              help={FACET_HELP[facet]}
              value={draft.weights[facet]}
              min={limits.weight[0]}
              max={limits.weight[1]}
              step={0.1}
              onChange={(v) => setWeight(facet, v)}
            />
          ))}

          <div className="card__foot" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn btn--primary" onClick={save} disabled={!dirty}>
              Save
            </button>
            <button className="btn" onClick={reset} disabled={atDefaults && !meta.saved}>
              Reset to code defaults
            </button>
            <button className="btn" onClick={rebuild} disabled={running || dirty}>
              {running ? 'Rebuilding…' : 'Rebuild and publish'}
            </button>
          </div>
          {saved && <div className="card__sub">{saved}</div>}
          {dirty && <div className="card__sub">Unsaved — Rebuild uses the saved values.</div>}
        </div>

        <div className="card">
          <div className="card__title">Preview</div>
          <div className="card__sub" style={{ marginBottom: 10 }}>
            Live, against the real catalog. Nothing is saved or published.
          </div>

          <select
            value={anchor}
            onChange={(e) => setAnchor(e.target.value)}
            style={{ width: '100%', marginBottom: 14 }}
          >
            {products.map((p) => (
              <option key={p.product_id} value={p.product_id}>
                {p.title} ({p.season})
              </option>
            ))}
          </select>

          {!result && <p>Ranking…</p>}
          {result && (
            <>
              {!result.has_sales && (
                <div className="card__sub" style={{ marginBottom: 10 }}>
                  No sales data on disk, so the sales slider has no effect yet.
                  Run the pipeline once to produce it.
                </div>
              )}
              <table className="table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Product</th>
                    <th style={{ textAlign: 'right' }}>Score</th>
                    <th style={{ textAlign: 'right' }}>Tags</th>
                    <th style={{ textAlign: 'right' }}>Sales</th>
                  </tr>
                </thead>
                <tbody>
                  {result.items.map((item, i) => (
                    <tr key={item.product_id}>
                      <td>{i + 1}</td>
                      <td>{item.title}</td>
                      <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                        {item.score.toFixed(3)}
                      </td>
                      <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                        {item.content_score.toFixed(3)}
                      </td>
                      <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                        {item.popularity.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="card__sub">
                <strong>Score</strong> is what ranks. <strong>Tags</strong> is
                the content match before sales; <strong>Sales</strong> is how
                well it sells, 0–1 against the catalog's best seller.
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
