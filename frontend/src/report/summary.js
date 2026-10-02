/*
 * The report's sentences, and its CSV.
 *
 * Pure: given what the API returned, work out what is worth SAYING about it.
 * A table of numbers makes the reader do that work, and different readers do
 * it differently - which is how "top selling is doing badly" and "top selling
 * is fine" get argued from the same screen.
 */
export function money(value, currency) {
  if (!value) return `${currency || 'USD'} 0`
  return `${currency || ''} ${Math.round(value).toLocaleString()}`.trim()
}

export function percent(value) {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

/* One row per block, measurements and money joined, no Seen. */
export function rows(data) {
  const measured = Object.fromEntries((data.blocks || []).map((b) => [b.block, b]))
  const earned = Object.fromEntries((data.revenue || []).map((r) => [r.block, r]))
  const ids = [...new Set([...Object.keys(measured), ...Object.keys(earned)])]

  return ids
    .map((id) => {
      const m = measured[id] || {}
      const e = earned[id] || {}
      return {
        block: id,
        label: id.replace(/_/g, ' '),
        impressions: m.impressions || 0,
        clicks: m.clicks || 0,
        click_rate: m.click_rate ?? null,
        add_to_cart: m.add_to_cart || 0,
        orders: e.orders || 0,
        revenue: e.revenue || 0,
        direct_revenue: e.direct_revenue || 0,
        direct_orders: e.direct_orders || 0,
        currency: e.currency || data.totals?.currency || '',
      }
    })
    .sort((a, b) => b.revenue - a.revenue || b.clicks - a.clicks)
}

/*
 * What stands out, in sentences. Only what the numbers support: a block with
 * no clicks at all gets "not placed, or never seen", never a verdict.
 */
export function notes(data, list) {
  const t = data.totals || {}
  const live = list.filter((r) => r.clicks > 0 || r.impressions > 0)
  const quiet = list.filter((r) => r.impressions === 0)
  const out = []

  const best = [...live].sort((a, b) => (b.click_rate || 0) - (a.click_rate || 0))[0]
  if (best && best.click_rate) {
    out.push(
      `${best.label} is clicked most often, at ${percent(best.click_rate)} of the times it is seen.`
    )
  }

  const earner = [...live].sort((a, b) => b.revenue - a.revenue)[0]
  if (earner && earner.revenue) {
    out.push(
      `${earner.label} is involved in the most sales: ${money(earner.revenue, earner.currency)} across ${earner.orders} orders.`
    )
  }

  const directTotal = list.reduce((sum, r) => sum + r.direct_revenue, 0)
  if (t.revenue) {
    const share = directTotal / t.revenue
    out.push(
      `Of ${money(t.revenue, t.currency)} in orders that involved a block, ` +
        `${money(directTotal, t.currency)} (${(share * 100).toFixed(0)}%) was the recommended products themselves. ` +
        `The rest is orders where the shopper clicked a recommendation and bought something else.`
    )
  }

  // Recently Viewed in the cart drawer records no card clicks by design - a
  // shopper adds from it rather than browsing to the product - so its zero is
  // expected and saying "clicked none" about it would send someone debugging
  // something that is not broken.
  const BY_DESIGN = { recently_viewed: 'adds straight from the drawer, so its cards are not click-tracked' }

  live
    .filter((r) => r.impressions > 500 && r.clicks === 0)
    .forEach((r) => {
      if (BY_DESIGN[r.block]) {
        out.push(
          `${r.label} shows no clicks because it ${BY_DESIGN[r.block]}. Its ${r.add_to_cart} adds are the number to read.`
        )
        return
      }
      out.push(
        `${r.label} was seen ${r.impressions.toLocaleString()} times and clicked none - it either has no clickable cards, or its clicks are not being recorded.`
      )
    })

  if (quiet.length) {
    out.push(
      `No traffic at all for ${quiet.map((r) => r.label).join(', ')} - not placed on the theme, or placed where nobody scrolls.`
    )
  }

  return out
}

export function csv(data, list) {
  const header = [
    'block', 'clicks', 'click rate', 'added to cart',
    'orders', 'revenue', 'direct revenue', 'direct orders', 'currency',
  ]
  const lines = [header.join(',')]

  list.forEach((r) => {
    lines.push([
      r.label,
      r.clicks,
      r.click_rate == null ? '' : (r.click_rate * 100).toFixed(2),
      r.add_to_cart,
      r.orders,
      r.revenue.toFixed(2),
      r.direct_revenue.toFixed(2),
      r.direct_orders,
      r.currency,
    ].join(','))
  })

  const t = data.totals || {}
  lines.push([
    'TOTAL', t.clicks || 0,
    t.click_rate == null ? '' : (t.click_rate * 100).toFixed(2),
    t.add_to_cart || 0, t.orders || 0,
    (t.revenue || 0).toFixed(2), (t.direct_revenue || 0).toFixed(2),
    t.direct_orders || 0, t.currency || '',
  ].join(','))

  return lines.join('\n')
}
