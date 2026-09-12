import { get, post, put } from '../api'

// Preview is a POST because it carries a tuning document, but it writes
// nothing — the backend requires no token for it. The shared post() sends one
// anyway, which is harmless.
export const getTuning = () => get('/tuning')
export const saveTuning = (tuning) => put('/tuning', { tuning })
export const resetTuning = () => put('/tuning', { tuning: null })
export const getProducts = () => get('/tuning/products')
export const previewTuning = (productId, tuning, limit = 10) =>
  post('/tuning/preview', { product_id: productId, tuning, limit })
