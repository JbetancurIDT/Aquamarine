import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ChatPage from './pages/ChatPage'
import DashboardPage from './pages/DashboardPage'
import PipelinePage from './pages/PipelinePage'
import AsesorPage from './pages/AsesorPage'
import AsesoresPage from './pages/AsesoresPage'
import PerformancePage from './pages/PerformancePage'
import MapaPage from './pages/MapaPage'
import MapaPropiedadPage from './pages/MapaPropiedadPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/chat/:origen" element={<ChatPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/pipeline" element={<PipelinePage />} />
        <Route path="/asesores" element={<AsesoresPage />} />
        <Route path="/asesor/:asesorId" element={<AsesorPage />} />
        <Route path="/performance" element={<PerformancePage />} />
        <Route path="/mapa" element={<MapaPage />} />
        <Route path="/mapa/propiedad/:codigo" element={<MapaPropiedadPage />} />
      </Routes>
    </BrowserRouter>
  )
}
