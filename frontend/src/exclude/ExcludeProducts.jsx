import Placeholder from '../components/Placeholder'

/*
 * The merchandiser override list: products that never appear in any block,
 * regardless of what the eligibility rule concludes.
 *
 * This is the screen that retires the Google Sheet (memory.md decision #9) —
 * a hand-maintained list drifts silently, and nobody notices until a product
 * nobody wants surfaced is on the homepage.
 */
export default function ExcludeProducts() {
  return (
    <Placeholder heading="Not built yet">
      <p>
        Two exclusion mechanisms will meet here. The automatic one already runs
        in the backend — the eligibility gate, which removes fixed-stock and{' '}
        <code>*SALE*</code> products, gift cards and anything without a product
        type. 421 active products, 252 eligible.
      </p>
      <p>
        The manual one is this screen: a merchandiser block list for the cases
        no rule can express. It replaces the Google Sheet of overrides, which
        was always meant to be temporary — a hand-maintained list goes stale
        without telling anyone.
      </p>
      <p>
        Worth showing here too: <em>why</em> each product was excluded. The
        backend already records the reason per product, and "why is this not
        showing" is the question this screen will actually be opened for.
      </p>
    </Placeholder>
  )
}
