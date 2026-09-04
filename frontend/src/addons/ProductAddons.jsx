import Placeholder from '../components/Placeholder'

// Another bundled Wiser feature, not a recommendation feature.
export default function ProductAddons() {
  return (
    <Placeholder heading="Not replaced by this project">
      <p>
        Upsell add-ons attached to a product are a merchandising feature, not a
        recommendation one. Out of scope here.
      </p>
      <p>
        Worth noting the catalog already has add-on products of its own —{' '}
        <code>Front &amp; Back Placement Add-on</code> sold 97 units in a
        fortnight. The eligibility gate now excludes them from every block,
        since an add-on service is not something to recommend.
      </p>
    </Placeholder>
  )
}
