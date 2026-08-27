import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

// Font di-bundle lokal (bukan CDN) supaya render konsisten saat screenshot
// dan saat demo tanpa jaringan. Tiga peran, sesuai DESIGN_BRIEF Bagian 2.2.
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/700.css'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'

import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App.jsx'
import { pasangTemaAwal } from './lib/tema.js'

// Dipasang sebelum render pertama supaya tidak ada kedip tema gelap→terang.
pasangTemaAwal()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
)
