import Placeholder from '../components/Placeholder'

// A Wiser product feature, not a recommendation feature. Listed in the nav so
// the web team can see it is gone on purpose.
export default function IntelliSearch() {
  return (
    <Placeholder heading="Not replaced by this project">
      <p>
        Search and filtering was a separate Wiser product bundled into the same
        app. This project replaces the recommendation blocks only.
      </p>
      <p>
        If search is relied on today, it needs its own decision before Wiser is
        uninstalled — the storefront's native Shopify search takes over, and
        that is a change worth knowing about in advance rather than discovering.
      </p>
    </Placeholder>
  )
}
