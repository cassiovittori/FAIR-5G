import { useState } from "react"
import { Link, Outlet, useLocation } from "react-router"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ChevronDown, ChevronLeft, LayoutGrid, Boxes, Activity, BookOpen } from "lucide-react"
import { useTranslation } from "react-i18next"
import { LanguageSwitcher } from "@/components/LanguageSwitcher"
import { ThemeToggle } from "@/components/theme-toggle"

const AMBIENTES_ITEMS = [
  { labelKey: "sidebar.activeEnvironments", to: "/pesquisador/ambientes-ativos" },
  { labelKey: "sidebar.allEnvironments", to: "/pesquisador/ambientes" },
] as const

export default function PesquisadorShell() {
  const { t } = useTranslation()
  const [collapsed, setCollapsed] = useState(false)
  const { pathname } = useLocation()

  const inMenu = pathname === "/pesquisador"
  const inAmbientes = pathname.startsWith("/pesquisador/ambientes") // inclui ambientes-ativos e /ambientes/:runId
  const inMonitoramento = pathname === "/pesquisador/monitoramento"

  // "Todos os Ambientes" também vale para o detalhe de um run
  const isSubActive = (to: string) =>
    to === "/pesquisador/ambientes"
      ? pathname === to || pathname.startsWith("/pesquisador/ambientes/")
      : pathname === to

  return (
    <div className="flex h-full">
      <aside className={`flex shrink-0 flex-col border-r bg-background transition-all ${collapsed ? "w-16" : "w-64"}`}>
        <div className="flex items-center justify-between p-4">
          {!collapsed && <span className="font-mono text-sm font-semibold">FAIR-5G</span>}
          <button onClick={() => setCollapsed((c) => !c)} className="text-muted-foreground">
            <ChevronLeft className={`h-4 w-4 transition-transform ${collapsed ? "rotate-180" : ""}`} />
          </button>
        </div>

        <div className="space-y-2 px-3">
          <Button className="w-full bg-[#0633FF] text-white hover:bg-[#0633FF]/90" asChild>
            <Link to="/pesquisador/novo">{collapsed ? "+" : t("sidebar.createEnvironment")}</Link>
          </Button>
          <Button
            variant={inMenu ? "secondary" : "ghost"}
            className={`w-full justify-center gap-2 ${inMenu ? "border border-[#0633FF] bg-muted text-foreground dark:border-white" : ""}`}
            asChild
          >
            <Link to="/pesquisador">
              <LayoutGrid className={`h-4 w-4 ${inMenu ? "text-[#0633FF] dark:text-white" : ""}`} />
              {!collapsed && t("sidebar.menu")}
            </Link>
          </Button>
        </div>

        {!collapsed && (
          <nav className="mt-6 flex-1 space-y-6 overflow-y-auto px-3">
            <div>
              <p className="px-2 text-xs font-medium text-muted-foreground">{t("sidebar.modules")}</p>
              <div className="mt-2 space-y-1">
                <Collapsible defaultOpen>
                  <CollapsibleTrigger
                    className={`group flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-muted ${
                      inAmbientes ? "font-medium text-foreground" : ""
                    }`}
                  >
                    <span className="flex items-center gap-2">
                      <Boxes className={`h-4 w-4 ${inAmbientes ? "text-[#0633FF]" : ""}`} />
                      {t("sidebar.environments")}
                    </span>
                    <ChevronDown className="h-3 w-3 transition-transform duration-200 group-data-[state=open]:rotate-180" />
                  </CollapsibleTrigger>
                  <CollapsibleContent className="ml-6 space-y-1 overflow-hidden border-l pl-3 data-[state=open]:animate-collapsible-down data-[state=closed]:animate-collapsible-up">
                    {AMBIENTES_ITEMS.map((item) => (
                      <Link
                        key={item.to}
                        to={item.to}
                        className={`flex items-center gap-2 rounded-md px-2 py-1 text-sm ${
                          isSubActive(item.to)
                            ? "font-medium text-foreground"
                            : "text-muted-foreground hover:text-foreground"
                        }`}
                      >
                        {/* sempre renderizada (invisível quando inativa) pro texto não pular ao trocar de aba */}
                        <span
                          aria-hidden
                          className={`h-1.5 w-1.5 shrink-0 rounded-full bg-current text-[#0633FF] transition-[opacity,scale] duration-500 ease-out ${
                            isSubActive(item.to) ? "glow-dot scale-100 opacity-100" : "scale-0 opacity-0"
                          }`}
                        />
                        {t(item.labelKey)}
                      </Link>
                    ))}
                  </CollapsibleContent>
                </Collapsible>

                <Link
                  to="/pesquisador/monitoramento"
                  className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                    inMonitoramento
                      ? "font-medium text-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <Activity className={`h-4 w-4 ${inMonitoramento ? "text-[#F5A623]" : ""}`} />
                  {t("sidebar.monitoring")}
                </Link>
              </div>
            </div>

            <div>
              <p className="px-2 text-xs font-medium text-muted-foreground">{t("sidebar.resources")}</p>
              <div className="mt-2 space-y-1">
                <Link to="/pesquisador/guia" className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground">
                  <BookOpen className="h-4 w-4" />
                  {t("sidebar.guide")}
                </Link>
              </div>
            </div>
          </nav>
        )}

        {/* recolhida (w-16) não cabe o seletor de idioma: fica só o tema */}
        <div className={`mt-auto flex items-center border-t p-3 ${collapsed ? "justify-center" : "justify-between"}`}>
          {!collapsed && <LanguageSwitcher />}
          <ThemeToggle />
        </div>
      </aside>

      <div className="min-w-0 flex-1 overflow-y-auto"><Outlet /></div>
    </div>
  )
}