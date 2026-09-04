import { STATUS_LABEL } from '../lib/nav'

export default function Header({ title, status }) {
  return (
    <header className="header">
      <h1 className="header__title">{title}</h1>
      {status && status !== 'planned' && (
        <span className={`badge ${status === 'n/a' ? 'is-na' : ''}`}>
          {STATUS_LABEL[status]}
        </span>
      )}
    </header>
  )
}
