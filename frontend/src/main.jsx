import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

// One page, tabs inside it — the AdminApp.jsx pattern from
// wholesale-order-entry. If the web team ever needs to link someone straight
// to Analytics, promote the tabs to paths using the PAGES-map pattern from
// that project's main.jsx. No router dependency either way.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
