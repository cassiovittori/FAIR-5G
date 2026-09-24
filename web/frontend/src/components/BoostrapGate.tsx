import { Navigate, Outlet } from "react-router"
import { useBootstrap } from "@/lib/bootstrap-context"

export function BootstrapGate() {
  const { status, checking } = useBootstrap()

  if (checking) {
    return <div className="p-6 text-sm text-muted-foreground">Carregando...</div>
  }

  if (!status?.bootstrapped) {
    return <Navigate to="/bootstrap" replace />
  }

  return <Outlet />
}