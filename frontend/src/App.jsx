import { useState } from 'react'
import { NAV, NAV_MORE } from './lib/nav'
import Sidebar from './components/Sidebar'
import Header from './components/Header'

import Dashboard from './dashboard/Dashboard'
import Analytics from './analytics/Analytics'
import ExcludeProducts from './exclude/ExcludeProducts'
import ManualUpdate from './run/ManualUpdate'
import Tuning from './tuning/Tuning'

// One component per nav entry. Adding a tab is: a folder, an entry in
// lib/nav.js, and a line here. No router, same as wholesale-order-entry.
const SCREENS = {
  dashboard: Dashboard,
  analytics: Analytics,
  exclude: ExcludeProducts,
  tuning: Tuning,
  run: ManualUpdate,
}

const ALL_NAV = [...NAV, ...NAV_MORE]

export default function App() {
  // Manual Update is the only screen that does something today, so it opens
  // there. Setup Widgets was the original landing screen and has been removed:
  // placement now lives in the Shopify theme editor.
  const [tab, setTab] = useState('run')

  const Screen = SCREENS[tab] || ManualUpdate
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
