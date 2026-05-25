import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/layout/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { SpeedPage } from './pages/SpeedPage'
import { HPPage } from './pages/HPPage'
import { ProtectPage } from './pages/ProtectPage'
import { DamagePage } from './pages/DamagePage'
import { PartyPage } from './pages/PartyPage'
import { HUDPage } from './pages/HUDPage'
import { MetaPage } from './pages/MetaPage'
import { HUDOverlay } from './components/hud/HUDOverlay'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* OBS HUD (透明背景、独立レイアウト) */}
        <Route path="/hud" element={<HUDOverlay />} />

        {/* メインダッシュボード */}
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/speed" element={<SpeedPage />} />
          <Route path="/hp" element={<HPPage />} />
          <Route path="/protect" element={<ProtectPage />} />
          <Route path="/damage" element={<DamagePage />} />
          <Route path="/party" element={<PartyPage />} />
          <Route path="/meta" element={<MetaPage />} />
          <Route path="/hud-settings" element={<HUDPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
