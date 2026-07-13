import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './hooks/useAuth'
import ProtectedRoute from './components/ProtectedRoute'
import AdminRoute from './components/AdminRoute'
import AppLayout from './components/layout/AppLayout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Clientes from './pages/Clientes'
import ClienteDetail from './pages/ClienteDetail'
import Tags from './pages/Tags'
import Usuarios from './pages/Usuarios'
import TaxasEntrega from './pages/TaxasEntrega'
import Locais from './pages/Locais'
import IFood from './pages/IFood'
import PDV from './pages/PDV'
import CatalogoPDV from './pages/CatalogoPDV'
import Vinculacoes from './pages/Vinculacoes'
import Eventos from './pages/Eventos'
import Orcamentos from './pages/Orcamentos'
import Notificacoes from './pages/Notificacoes'
import Configuracoes from './pages/Configuracoes'
import Catalogo from './pages/Catalogo'
import FichasTecnicas from './pages/FichasTecnicas'
import CentralPrecos from './pages/CentralPrecos'
import Relatorios from './pages/Relatorios'
import Auditoria from './pages/Auditoria'



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
            <Route path="taxas-entrega" element={<TaxasEntrega />} />
            <Route path="integracoes/ifood" element={<IFood />} />
            <Route path="integracoes/anotaai" element={<Placeholder title="Anota AI" />} />
            <Route path="integracoes/pdv" element={<PDV />} />
            <Route path="configuracoes" element={<Configuracoes />} />
            <Route path="integracoes/pdv/catalogo" element={<CatalogoPDV />} />
            <Route path="/vinculacoes" element={<Vinculacoes />} />
            <Route path="eventos" element={<Eventos />} />
            <Route path="orcamentos" element={<Orcamentos />} />
            <Route path="locais-evento" element={<Locais />} />
            <Route path="notificacoes" element={<Notificacoes />} />
            <Route path="catalogo" element={<Catalogo />} />
            <Route path="fichas-tecnicas" element={<FichasTecnicas />} />
            <Route path="central-precos" element={<CentralPrecos />} />
            <Route path="relatorios/ifood" element={<Relatorios />} />
            <Route path="auditoria" element={<AdminRoute><Auditoria /></AdminRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
