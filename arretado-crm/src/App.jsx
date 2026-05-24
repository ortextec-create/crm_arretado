import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './hooks/useAuth'
import ProtectedRoute from './components/ProtectedRoute'
import AppLayout from './components/layout/AppLayout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Clientes from './pages/Clientes'
import ClienteDetail from './pages/ClienteDetail'
import Tags from './pages/Tags'
import Usuarios from './pages/Usuarios'
import IFood from './pages/IFood'
import PDV from './pages/PDV'
import CatalogoPDV from './pages/CatalogoPDV'



function Placeholder({ title }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%' }}>
      <div style={{ padding:'22px 26px', borderBottom:'1px solid var(--border)', fontFamily:"'Playfair Display',serif", fontSize:18, color:'var(--texto)' }}>
        {title}
      </div>
      <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', flexDirection:'column', gap:12, color:'var(--texto-muted)' }}>
        <i className="ti ti-clock" style={{ fontSize:32, opacity:0.3 }} />
        <p style={{ fontSize:13 }}>Em desenvolvimento — Fase 3</p>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="clientes" element={<Clientes />} />
            <Route path="clientes/:id" element={<ClienteDetail />} />
            <Route path="tags" element={<Tags />} />
            <Route path="usuarios" element={<Usuarios />} />
            <Route path="integracoes/ifood" element={<IFood />} />
            <Route path="integracoes/anotaai" element={<Placeholder title="Anota AI" />} />
            <Route path="integracoes/pdv" element={<PDV />} />
            <Route path="configuracoes" element={<Placeholder title="Configurações" />} />
            <Route path="integracoes/pdv/catalogo" element={<CatalogoPDV />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
