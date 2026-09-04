import Placeholder from '../components/Placeholder'

/*
 * Wiser's billing screen. Kept in the nav for one reason: it is the clearest
 * statement of what this project is for.
 */
export default function MyPlan() {
  return (
    <Placeholder heading="No plan, no invoice">
      <p>
        This screen was Wiser's subscription and usage limits. There is nothing
        to put here — the recommendations are computed from your own Shopify
        data, on your own machine.
      </p>
      <p>
        Removing the vendor cost was never the main reason for building this.
        Owning the logic was: being able to see why a product was recommended,
        and stop it recommending something you do not want surfaced.
      </p>
    </Placeholder>
  )
}
