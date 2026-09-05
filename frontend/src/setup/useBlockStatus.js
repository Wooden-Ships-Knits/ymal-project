import { useEffect, useState } from 'react'
import { getBlockStatus } from './api'

/*
 * Server-side block status, merged over the static list in lib/blocks.js.
 *
 * The static list stays as the fallback (spec section 7): if this fetch fails
 * the console still renders every card, it just cannot warn about unpublished
 * lists. A blank console would be worse than a console missing one warning.
 */
export default function useBlockStatus() {
  const [byId, setById] = useState({})
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    getBlockStatus()
      .then((blocks) => {
        setById(Object.fromEntries(blocks.map((b) => [b.id, b])))
        setLoaded(true)
      })
      .catch(() => setLoaded(false))
  }, [])

  return { byId, loaded }
}
