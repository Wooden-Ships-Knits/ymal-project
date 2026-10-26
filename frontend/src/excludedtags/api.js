import { get, put } from '../api'

// Tags whose products Top Selling (MYNTS) and Trending stop recommending -
// ymal/excluded_tags.py has the why.
export const getExcludedTags = () => get('/excluded-tags')
export const saveExcludedTags = (tags) => put('/excluded-tags', { tags })
