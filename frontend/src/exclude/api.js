import { get, put } from '../api'

// The merchandiser block list — products that must never appear in any block,
// whatever the eligibility rule says. This is where the Google Sheet of
// overrides was always heading (memory.md decision #9).
export const getExclusions = () => get('/exclusions')
export const saveExclusions = (productIds) => put('/exclusions', { product_ids: productIds })
