import { Navigate, Outlet } from "react-router"
import { useTranslation } from "react-i18next"
import { useBootstrap } from "@/lib/bootstrap-context"

export function BootstrapGate() {
  const { t } = useTranslation()
  const { status, checking } = useBootstrap()

  if (checking) {
    return <div className="p-6 text-sm text-muted-foreground">{t("common.loading")}</div>
  }

  if (!status?.bootstrapped) {
    return <Navigate to="/bootstrap" replace />
  }

  return <Outlet />
}