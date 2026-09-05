import { useState } from 'react'
import { setToken } from './useToken'

/*
 * Shown when a write comes back 401. Not a login screen — the console reads
 * fine without it, and this only appears at the moment someone tries to change
 * something.
 */
export default function TokenPrompt({ onSubmit, onCancel }) {
  const [value, setValue] = useState('')

  const submit = (event) => {
    event.preventDefault()
    if (!value) return
    setToken(value)
    onSubmit()
  }

  return (
    <form className="note" onSubmit={submit} style={{ marginBottom: 18 }}>
      <h3>Password needed to save</h3>
      <p>
        Saving writes to the live Shopify shop. Ask the web team for the console
        password if you do not have it.
      </p>
      <input
        type="password"
        value={value}
        autoFocus
        onChange={(e) => setValue(e.target.value)}
        style={{ padding: '6px 8px', minWidth: 260, marginRight: 8 }}
      />
      <button type="submit">Save and retry</button>
      <button type="button" onClick={onCancel} style={{ marginLeft: 8 }}>
        Cancel
      </button>
    </form>
  )
}
