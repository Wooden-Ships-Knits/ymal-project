import { useEffect, useState } from 'react'
import { getAnalytics } from '../analytics/api'
import RangePicker from '../analytics/RangePicker'
import { csv, money, notes, percent, rows } from './summary'

/*
 * The overview, written out.
 *
 * The Analytics screen is for looking things up; this is for sending to
 * someone. It says in sentences what the table leaves the reader to work out,
 * and downloads as a spreadsheet for anyone who would rather have the numbers.
 *
 * NO "SEEN" COLUMN. The web team asked for it gone: six-figure impression
 * counts dominate a page whose point is what the blocks EARNED, and the click
 * rate already carries that denominator.
 */
export default function Report() {
  const [days, setDays] = useState(30)
  const [range, setRange] = useState(null)
  const [draft, setDraft] = useState({ start: '', end: '' })
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    setData(null)
    getAnalytics(days, range)
      .then(setData)
      .catch((err) => setError(err.message))
  }, [days, range])

  function download() {
    const blob = new Blob([csv(data, list)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `ymal-report-${data.start}-to-${data.end}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const picker = (
    <RangePicker
      days={days}
      range={range}
      draft={draft}
      onDays={(n) => {
        setRange(null)
        setDraft({ start: '', end: '' })
        setDays(n)
      }}
      onDraft={setDraft}
      onApply={() => setRange({ ...draft })}
      onClear={() => {
        setRange(null)
        setDraft({ start: '', end: '' })
      }}
    />
  )

  if (error) {
    return (
      <>
        {picker}
        <div className="note" style={{ borderLeftColor: '#b85450' }}>
          <h3>Report unavailable</h3>
          <p><code>{error}</code></p>
        </div>
      </>
    )
  }

  if (!data) return <>{picker}<p>Loading…</p></>

  const t = data.totals || {}
  const list = rows(data)
  const said = notes(data, list)
  const attributed = data.freshness?.orders_through

  return (
    <>
      {picker}

      <div className="card" style={{ marginBottom: 16 }}>
        <h2 style={{ marginTop: 0 }}>
          YMAL performance, {data.start} to {data.end}
        </h2>

        <p>
          Blocks were clicked <strong>{(t.clicks || 0).toLocaleString()}</strong> times
          {t.click_rate != null && <> ({percent(t.click_rate)} of the times they were seen)</>},
          leading to <strong>{(t.add_to_cart || 0).toLocaleString()}</strong> add-to-carts
          and <strong>{(t.orders || 0).toLocaleString()}</strong> orders
          worth <strong>{money(t.revenue, t.currency)}</strong>,
          of which <strong>{money(t.direct_revenue, t.currency)}</strong> was the recommended
          products themselves.
        </p>

        <ul>
          {said.map((line) => (
            <li key={line} style={{ marginBottom: 4 }}>{line}</li>
          ))}
        </ul>

        <p className="card__sub">
          Revenue counts the whole order whenever a block was clicked first, even if the
          shopper bought something else; direct counts only the recommended product, in the
          orders that contained it. Neither says the block CAUSED the sale.
          {attributed && <> Orders attributed up to {attributed.slice(0, 16).replace('T', ' ')} UTC
            — run Manual Update to bring it to today.</>}
        </p>

        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <button type="button" className="btn btn--primary" onClick={download}>
            Download CSV
          </button>
          <button type="button" className="btn" onClick={() => window.print()}>
            Print / save as PDF
          </button>
        </div>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Block</th>
            <th style={{ textAlign: 'right' }}>Clicks</th>
            <th style={{ textAlign: 'right' }}>Click rate</th>
            <th style={{ textAlign: 'right' }}>Added to cart</th>
            <th style={{ textAlign: 'right' }}>Orders</th>
            <th style={{ textAlign: 'right' }}>Revenue</th>
            <th style={{ textAlign: 'right' }}>Direct</th>
          </tr>
        </thead>
        <tbody>
          {list.map((r) => (
            <tr key={r.block}>
              <td>{r.label}</td>
              <td style={{ textAlign: 'right' }}>{r.clicks.toLocaleString()}</td>
              <td style={{ textAlign: 'right' }}>{percent(r.click_rate)}</td>
              <td style={{ textAlign: 'right' }}>{r.add_to_cart.toLocaleString()}</td>
              <td style={{ textAlign: 'right' }}>{r.orders || '—'}</td>
              <td style={{ textAlign: 'right' }}>{r.revenue ? money(r.revenue, r.currency) : '—'}</td>
              <td style={{ textAlign: 'right' }}>
                {r.direct_revenue ? money(r.direct_revenue, r.currency) : '—'}
                {r.direct_orders ? <span className="card__sub"> ({r.direct_orders})</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}
