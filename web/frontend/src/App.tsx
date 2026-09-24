import './App.css'
import { Routes, Route, Navigate } from 'react-router'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ListaAmbientes from './pages/ListaAmbientes'
import Trilha from './pages/Trilha'
import Bootstrap from './pages/Bootstrap'
import ProtectedRoute from './components/ProtectedRoute'
import { BootstrapGate } from './components/BoostrapGate'
import AppShell from './components/AppShell'
import PesquisadorShell from './components/PesquisadorShell'
import PesquisadorHome from './pages/pesquisador/PesquisadorHome'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/bootstrap" element={<Bootstrap />} />

        <Route element={<BootstrapGate />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route element={<AppShell />}>
            <Route element={<PesquisadorShell />}>
              <Route path="/pesquisador" element={<PesquisadorHome />} />
            </Route>
            <Route path="/tutorial" element={<Trilha />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  )
}

export default App
