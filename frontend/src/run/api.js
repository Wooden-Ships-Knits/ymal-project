import { get, post } from '../api'

// GET is open; POST carries the write token, because a run ends by publishing
// to the live shop.
export const getRunStatus = () => get('/run')
export const startRun = (skipCopurchase) =>
  post('/run', { skip_copurchase: skipCopurchase })
