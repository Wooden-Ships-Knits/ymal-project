import { get, put } from '../api'

// Product titles whose YMAL cards link to the product page instead of adding
// to the cart - ymal/personalized.py has the why.
export const getPersonalized = () => get('/personalized')
export const savePersonalized = (titles) => put('/personalized', { titles })
