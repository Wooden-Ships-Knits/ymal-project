import Placeholder from '../components/Placeholder'

/*
 * Wiser has a language selector. Whether this store needs one has never been
 * asked, so this stays a stub rather than an assumption.
 */
export default function Translations() {
  return (
    <Placeholder heading="Open question, not a plan">
      <p>
        Only the block headings are ours to translate — every other word in a
        block is product data, which Shopify already localises.
      </p>
      <p>
        Whether this store sells in more than one language has not been
        confirmed. If it does not, this screen never gets built and the config
        stays single-locale. If it does, headings become a map keyed by locale
        rather than a string, which is a change to{' '}
        <code>docs/config-contract.md</code> — so it is worth answering before
        the schema settles rather than after.
      </p>
    </Placeholder>
  )
}
