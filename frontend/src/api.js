/*
 * Shared fetch wrapper. Every feature folder has its own api.js for its own
 * endpoints; this holds only what they all need.
 *
 * The console talks to our FastAPI backend and nothing else. It never holds a
 * Shopify credential — the backend does, and it is the only thing that talks
 * to Shopify.
 */
import { getToken } from './auth/useToken'

const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...options,
  })

  let body = null
  try {
    body = await res.json()
  } catch (e) {
    /* an empty or non-JSON body is fine for some responses */
  }

  if (!res.ok) {
    // 422 carries field-level validation errors from the backend. Surface them
    // intact — "slots must be between 2 and 12" is more use than "failed".
    const err = new Error(body?.detail || body?.message || `Request failed (${res.status})`)
    err.status = res.status
    err.errors = body?.errors || []
    throw err
  }
  return body
}

// Writes carry the token; reads do not need one. The header name matches
// app/main.py's require_token.
const withToken = (options) => ({
  ...options,
  headers: { 'Content-Type': 'application/json', 'X-YMAL-Token': getToken() },
})

export const get = (path) => request(path)
export const put = (path, data) =>
  request(path, withToken({ method: 'PUT', body: JSON.stringify(data) }))
export const post = (path, data) =>
  request(path, withToken({ method: 'POST', body: JSON.stringify(data) }))
