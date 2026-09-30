import { get } from '../api'

// Either the rolling window the preset buttons use, or a pair of calendar
// dates. `range` is { start, end } - both are sent or neither is, because half
// a range is an error the API would rightly refuse.
export const getAnalytics = (days, range) =>
  get(
    range && range.start && range.end
      ? `/analytics?start=${range.start}&end=${range.end}`
      : `/analytics?days=${days}`
  )

// Probes the PUBLIC tracking URL from the API, through the VM's nginx - the
// only path a shopper's browser can take. Answers "is it installed but broken"
// versus "nobody has clicked yet", which look identical from a table of zeroes.
export const getTrackingHealth = () => get('/tracking-health')
