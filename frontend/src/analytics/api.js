import { get } from '../api'

export const getAnalytics = (days) => get(`/analytics?days=${days}`)

// Probes the PUBLIC tracking URL from the API, through the VM's nginx - the
// only path a shopper's browser can take. Answers "is it installed but broken"
// versus "nobody has clicked yet", which look identical from a table of zeroes.
export const getTrackingHealth = () => get('/tracking-health')
