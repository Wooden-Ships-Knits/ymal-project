import { useState } from 'react'

/*
 * Revenue and clicks over time.
 *
 * ONE measure at a time, chosen by the toggle. Revenue and clicks have
 * different scales and units, and drawing both against two y-axes is the
 * single most misleading thing a chart like this can do - the crossing point
 * of the two lines would be an artefact of the axis choice, not the data.
 *
 * Inline SVG rather than a charting library: one series, one scale, and the
 * whole thing is about forty lines.
 */
const PAD = { top: 12, right: 16, bottom: 26, left: 52 }
const W = 900
const H = 220

const METRICS = [
  { id: 'revenue', label: 'Revenue' },
  { id: 'clicks', label: 'Clicks' },
]

function niceCeiling(value) {
  // Round the top of the scale up to a number a person would choose, so the
  // axis reads 1,250 rather than 1,076.
  //
  // Stepped at 1/1.25/1.5/2/2.5/3/4/5/7.5/10 rather than whole powers of ten:
  // rounding 1,076 up to 2,000 leaves half the plot empty and flattens the
  // shape of the data into the bottom of the frame.
  if (value <= 0) return 1
  const magnitude = Math.pow(10, Math.floor(Math.log10(value)))
  const steps = [1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10]
  const scaled = value / magnitude
  return (steps.find((s) => scaled <= s) || 10) * magnitude
}

function niceStep(rough) {
  // A gridline interval a person would choose: 1, 2, 2.5 or 5 times a power
  // of ten. Every label is then a round number.
  if (rough <= 0) return 1
  const magnitude = Math.pow(10, Math.floor(Math.log10(rough)))
  const scaled = rough / magnitude
  const step = [1, 2, 2.5, 5, 10].find((s) => scaled <= s) || 10
  return step * magnitude
}

function shortDate(iso) {
  const [, m, d] = iso.split('-')
  return `${Number(d)}/${Number(m)}`
}

export default function TrendChart({ daily, currency }) {
  const [metric, setMetric] = useState('revenue')
  const [hover, setHover] = useState(null)

  const values = daily.map((d) => d[metric])
  const peak = Math.max(...values, 0)
  // The gridline step is chosen first, then the ceiling rounded up to a
  // multiple of it. Choosing the ceiling first gave labels like 313 and 938,
  // because a nice ceiling does not necessarily divide into nice quarters.
  const step = niceStep(niceCeiling(peak) / 4)
  const max = Math.max(step * Math.ceil(niceCeiling(peak) / step), step)
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom

  const x = (i) =>
    PAD.left + (daily.length < 2 ? innerW / 2 : (i / (daily.length - 1)) * innerW)
  const y = (v) => PAD.top + innerH - (v / max) * innerH

  const line = values.map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join(' ')
  const area = `${line} L${x(values.length - 1)},${PAD.top + innerH} L${x(0)},${
    PAD.top + innerH
  } Z`

  // Four gridlines is enough to read a value off; more is chartjunk.
  // Ticks are multiples of the step, so each one is a round number and the
  // topmost sits exactly on the ceiling.
  const ticks = []
  for (let t = 0; t <= max + 1e-9; t += step) ticks.push(t)

  const format = (v) =>
    metric === 'revenue'
      ? `${currency || ''} ${v.toLocaleString()}`.trim()
      : v.toLocaleString()

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div className="chart__head">
        <h3 className="card__title">Over time</h3>
        <div>
          {METRICS.map((m) => (
            <button
              key={m.id}
              type="button"
              className="btn"
              aria-pressed={metric === m.id}
              onClick={() => setMetric(m.id)}
              style={{
                marginLeft: 6,
                fontWeight: metric === m.id ? 600 : 400,
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="chart"
        role="img"
        aria-label={`${metric} per day for the last ${daily.length} days`}
        onMouseLeave={() => setHover(null)}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(t)}
              y2={y(t)}
              className="chart__grid"
            />
            <text x={PAD.left - 8} y={y(t) + 4} className="chart__tick" textAnchor="end">
              {t.toLocaleString()}
            </text>
          </g>
        ))}

        <path d={area} className="chart__area" />
        <path d={line} className="chart__line" />

        {/* Only the ends are labelled - a date under every point is unreadable
            at 30 days and pointless at 90. */}
        {daily.length > 0 && (
          <>
            <text x={x(0)} y={H - 8} className="chart__tick" textAnchor="start">
              {shortDate(daily[0].day)}
            </text>
            <text x={x(daily.length - 1)} y={H - 8} className="chart__tick" textAnchor="end">
              {shortDate(daily[daily.length - 1].day)}
            </text>
          </>
        )}

        {hover !== null && (
          <>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={PAD.top}
              y2={PAD.top + innerH}
              className="chart__crosshair"
            />
            <circle cx={x(hover)} cy={y(values[hover])} r="4.5" className="chart__dot" />
          </>
        )}

        {/* Invisible hit areas, wider than the marks, so hovering is easy. */}
        {daily.map((d, i) => (
          <rect
            key={d.day}
            x={x(i) - innerW / (daily.length * 2)}
            y={PAD.top}
            width={innerW / daily.length}
            height={innerH}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}
      </svg>

      <p className="card__sub" style={{ margin: '6px 0 0', minHeight: 18 }}>
        {hover !== null
          ? `${daily[hover].day} — ${format(values[hover])}`
          : `Peak ${format(Math.max(...values, 0))}`}
      </p>
    </div>
  )
}
