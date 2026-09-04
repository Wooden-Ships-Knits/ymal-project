import { get } from '../api'

// Reads the event store. Nothing here exists until the event endpoint and its
// Postgres table do — see docs/ymal-flow.drawio page 7.
export const getBlockMetrics = (from, to) =>
  get(`/analytics?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`)
