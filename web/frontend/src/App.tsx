import './App.css'
import { Routes, Route, Navigate } from 'react-router'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ListaAmbientes from './pages/ListaAmbientes'
import Trilha from './pages/Trilha'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" />} />
      <Route path="/login" element={<Login />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/pesquisador" element={<ListaAmbientes />} />
      <Route path="/trilha" element={<Trilha />} />
    </Routes>
  )
}

export default App
