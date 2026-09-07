import { get, put, post } from '../api'

// The only endpoints that write anything. Everything the console does to the
// storefront happens through PUT /api/config — see docs/config-contract.md.
export const getConfig = () => get('/config')
export const saveConfig = (config) => put('/config', config)
export const undoConfig = () => post('/config/undo')
export const getBlockStatus = () => get('/blocks')
