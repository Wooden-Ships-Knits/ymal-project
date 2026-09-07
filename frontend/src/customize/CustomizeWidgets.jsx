import Placeholder from '../components/Placeholder'

/*
 * Appearance: headings, grid vs carousel, how many columns on mobile.
 *
 * Later on purpose. The heading text is already editable per block in Setup
 * Widgets, which covers the change the web team will actually want to make.
 * Everything else here risks letting someone restyle a card away from the
 * theme's own — and looking native is the whole reason the storefront fetches
 * cards from the theme rather than building them in JavaScript.
 */
export default function CustomizeWidgets() {
  return (
    <Placeholder heading="Later — and deliberately narrow when it comes">
      <p>
        Headings are already editable per block in <strong>Setup Widgets</strong>,
        which is the change worth making often. What is left for this screen is
        layout: grid or carousel, columns per breakpoint, spacing.
      </p>
      <p>
        One thing this screen should <em>not</em> offer is restyling the product
        card. The storefront fetches cards from the theme itself
        (<code>?view=ymal-card</code>) precisely so the blocks look native and
        stay that way when the theme changes. A colour picker here would undo
        that.
      </p>
    </Placeholder>
  )
}
