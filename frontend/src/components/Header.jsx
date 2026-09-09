import { STATUS_LABEL } from '../lib/nav'

export default function Header({ title, status }) {
  return (
    <header className="header">
      <h1 className="header__title">{title}</h1>
      {/* A badge is only worth drawing when it says something. 'live' has no
          label, and 'planned' is already obvious from an empty screen. */}
      {status && STATUS_LABEL[status] && status !== 'planned' && (
        <span className={`badge ${status === 'n/a' ? 'is-na' : ''}`}>
          {STATUS_LABEL[status]}
        </span>
      )}
    </header>
  )
}
