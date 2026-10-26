import { useEffect, useState } from 'react'
import { marked } from 'marked'
import { getVersion } from './api'

/*
 * What changed, and when — docs/version.md, rendered.
 *
 * This was a placeholder saying a dashboard summarises other screens and there
 * was nothing to summarise yet. True, but it meant the first screen the web
 * team saw said nothing. Release notes are the one thing that IS worth reading
 * on opening the console: which behaviour changed, and whether the thing you
 * are about to blame was already fixed.
 *
 * The markdown comes from our own repository, not from a user, so rendering it
 * as HTML is safe. If that ever stops being true — a notes file someone can
 * edit through the console, say — this needs sanitising first.
 */
export default function Dashboard() {
  const [html, setHtml] = useState('')
  const [detail, setDetail] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    getVersion()
      .then((body) => {
        setHtml(body.markdown ? marked.parse(body.markdown) : '')
        setDetail(body.detail || '')
      })
      .catch((err) => setError(err.message))
  }, [])

  if (error) return <p className="note">{error}</p>
  if (!html && !detail) return <p>Loading…</p>

  // A missing file is not an error worth a red banner — the console still
  // works. Say what is missing and how to fix it, and move on.
  if (!html) {
    return (
      <div className="note">
        <h3>No release notes</h3>
        <p>{detail}</p>
      </div>
    )
  }

  return (
    <div className="card">
      <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  )
}
