import { get } from '../api'

export const getAnalytics = (days) => get(`/analytics?days=${days}`)
