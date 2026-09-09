import { useEffect, useRef, useState } from 'react'
import { getRunStatus, startRun } from './api'
import TokenPrompt from '../auth/TokenPrompt'

/*
 * Run the pipeline now, instead of waiting for 20:00 Makassar.
 *
 * The chain takes about three minutes, so the button starts it and the page
 * polls. Polling only while a run is going: an idle console has no reason to
 * ask the server anything.
 */
const POLL_MS = 3000

function when(iso) {
  if (!iso) return null
  return new Date(iso).toLocaleString()
}

export default function ManualUpdate() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')
  const [needsToken, setNeedsToken] = useState(false)
  const [skipCopurchase, setSkipCopurchase] = useState(false)
  const timer = useRef(null)

  const refresh = () =>
    getRunStatus()
      .then(setStatus)
      .catch((err) => setError(err.message))

  useEffect(() => {
    refresh()
    return () => clearInterval(timer.current)
  }, [])

  // Poll only while something is actually running.
  useEffect(() => {
    clearInterval(timer.current)
    if (status?.running) {
      timer.current = setInterval(refresh, POLL_MS)
    }
    return () => clearInterval(timer.current)
  }, [status?.running])

  const begin = () => {
    setError('')
    startRun(skipCopurchase)
      .then((next) => {
        setNeedsToken(false)
        setStatus(next)
      })
      .catch((err) => {
        if (err.status === 401) setNeedsToken(true)
        else setError(err.message)
      })
  }

  if (!status) return <p>Loading…</p>

  const running = status.running
  const progress = status.total_steps
    ? `step ${status.step_number} of ${status.total_steps}`
    : ''

  return (
    <>
      {needsToken && (
        <TokenPrompt onSubmit={begin} onCancel={() => setNeedsToken(false)} />
      )}

      <div className="note" style={{ marginBottom: 18 }}>
        <h3>What this does</h3>
        <p>
          Rebuilds the eligible product list, the feature table, the
          recommendation pools and the three store-wide lists, then publishes
          all of it to Shopify. The same six steps the nightly schedule runs at
          20:00 Makassar.
        </p>
        <p>
          Worth running after changing the eligibility rule, or when the
          catalog has moved and you do not want to wait for tonight. It takes
          about three minutes.
        </p>
      </div>

      {running ? (
        <div className="note" style={{ marginBottom: 18 }}>
          <h3>Running now — {progress}</h3>
          <p>
            <code>{status.step}</code>
          </p>
          <p>
            Started {when(status.started_at)}. This page updates itself; you can
            leave it and come back.
          </p>
        </div>
      ) : (
        <p style={{ marginBottom: 18 }}>
          <button type="button" onClick={begin}>
            Run the pipeline now
          </button>{' '}
          <label style={{ marginLeft: 12, fontSize: 13 }}>
            <input
              type="checkbox"
              checked={skipCopurchase}
              onChange={(e) => setSkipCopurchase(e.target.checked)}
            />{' '}
            Skip co-purchase
          </label>
        </p>
      )}

      {!running && skipCopurchase && (
        <p className="card__sub" style={{ marginBottom: 18 }}>
          Co-purchase pulls a year of orders and is most of the running time.
          Skipping it keeps yesterday&apos;s reranking, which barely moves day
          to day.
        </p>
      )}

      {status.finished_at && !running && (
        <div
          className="note"
          style={{
            marginBottom: 18,
            borderLeftColor: status.ok ? undefined : '#b85450',
          }}
        >
          <h3>{status.ok ? 'Last run succeeded' : 'Last run failed'}</h3>
          <p>Finished {when(status.finished_at)}.</p>
          {status.skipped_copurchase && <p>Co-purchase was skipped.</p>}
          {status.error && (
            <p>
              <code>{status.error}</code>
            </p>
          )}
        </div>
      )}

      {error && (
        <div className="note" style={{ borderLeftColor: '#b85450' }}>
          <h3>Not connected to the backend</h3>
          <p>
            <code>{error}</code>
          </p>
        </div>
      )}
    </>
  )
}
