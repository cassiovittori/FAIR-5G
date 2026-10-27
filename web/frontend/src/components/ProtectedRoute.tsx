import { Navigate, Outlet } from "react-router"
import { useTranslation } from "react-i18next"
import { useAuth } from "@/lib/auth"

export default function ProtectedRoute() {
  const { t } = useTranslation()
  const { user, loading } = useAuth()

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center">{t("common.loading")}</div>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}