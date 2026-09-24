import { Navigate, Outlet } from "react-router"
import { useAuth } from "@/lib/auth"

export default function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center">Carregando...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}