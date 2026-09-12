import { get } from '../api'

// Release notes as markdown. The backend reads docs/version.md, which
// docker-compose mounts into the api container read-only.
export const getVersion = () => get('/version')
