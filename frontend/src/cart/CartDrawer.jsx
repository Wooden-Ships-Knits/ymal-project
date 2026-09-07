import Placeholder from '../components/Placeholder'

/*
 * Wiser ships its own cart drawer. We do not — the theme already has one.
 *
 * What we do need is a PLACEMENT inside it, and that belongs in Setup Widgets
 * with every other placement rather than on a screen of its own.
 */
export default function CartDrawer() {
  return (
    <Placeholder heading="Not a screen — a placement">
      <p>
        Wiser replaces the theme's cart drawer with its own. This project does
        not: the theme's drawer stays, and blocks are placed inside it like
        anywhere else.
      </p>
      <p>
        Configure it under <strong>Setup Widgets → Cart Page</strong>. It is
        v2, and it is the placement with the highest expected impact on order
        value.
      </p>
      <p>
        One design question to settle first: Featured needs a product to be
        about, and a cart holds several. Which item is the anchor when there are
        four? That has to be answered before Featured can go in a cart.
      </p>
    </Placeholder>
  )
}
