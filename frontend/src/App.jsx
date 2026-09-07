import { useState } from 'react'
import { NAV, NAV_MORE } from './lib/nav'
import Sidebar from './components/Sidebar'
import Header from './components/Header'

import Dashboard from './dashboard/Dashboard'
import SetupWidgets from './setup/SetupWidgets'
import Recommendations from './recommendations/Recommendations'
import CustomizeWidgets from './customize/CustomizeWidgets'
import IntelliSearch from './search/IntelliSearch'
import ProductAddons from './addons/ProductAddons'
import Analytics from './analytics/Analytics'
import CartDrawer from './cart/CartDrawer'
import MyPlan from './plan/MyPlan'
import ExcludeProducts from './exclude/ExcludeProducts'
import Translations from './translations/Translations'
import FlushCache from './cache/FlushCache'

// One component per nav entry. Adding a tab is: a folder, an entry in
// lib/nav.js, and a line here. No router, same as wholesale-order-entry.
const SCREENS = {
  dashboard: Dashboard,
  setup: SetupWidgets,
  recommendations: Recommendations,
  customize: CustomizeWidgets,
  search: IntelliSearch,
  addons: ProductAddons,
  analytics: Analytics,
  cart: CartDrawer,
  plan: MyPlan,
  exclude: ExcludeProducts,
  translations: Translations,
  cache: FlushCache,
}

const ALL_NAV = [...NAV, ...NAV_MORE]

export default function App() {
  // Setup Widgets is the screen this console exists for, so it opens there.
  const [tab, setTab] = useState('setup')

  const Screen = SCREENS[tab] || SetupWidgets
  const entry = ALL_NAV.find((n) => n.id === tab)

  return (
    <div className="app">
      <Sidebar active={tab} onSelect={setTab} />
      <main className="main">
        <Header title={entry?.label || ''} status={entry?.status} />
        <div className="content">
          <Screen />
        </div>
      </main>
    </div>
  )
}
