/*
 * The console's write token.
 *
 * sessionStorage, never localStorage and never a VITE_ env var. A VITE_
 * variable is compiled into the bundle and readable by anyone who opens the
 * page, which would make a shared secret public. sessionStorage dies with the
 * tab, so a shared machine does not keep it.
 */
const KEY = 'ymal:token'

export function getToken() {
  try {
    return sessionStorage.getItem(KEY) || ''
  } catch (e) {
    // Private browsing throws rather than returning null.
    return ''
  }
}

export function setToken(value) {
  try {
    sessionStorage.setItem(KEY, value)
  } catch (e) {
    /* the write still works this session; it just will not survive a reload */
  }
}

export function clearToken() {
  try {
    sessionStorage.removeItem(KEY)
  } catch (e) {
    /* nothing to clear */
  }
}
