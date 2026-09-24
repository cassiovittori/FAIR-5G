import { useState } from "react"
import { Link, Outlet, useLocation } from "react-router"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ChevronDown, ChevronLeft, LayoutGrid, Boxes, Activity, BookOpen } from "lucide-react"

const AMBIENTES_ITEMS = [
  { label: "Ambientes Ativos", to: "/pesquisador/ambientes-ativos" },
  { label: "Todos os Ambientes", to: "/pesquisador/ambientes" },
]

export default function PesquisadorShell() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()

  return (
    <div className="flex min-h-screen">
      <aside className={`flex flex-col border-r bg-background transition-all ${collapsed ? "w-16" : "w-64"}`}>
        <div className="flex items-center justify-between p-4">
          {!collapsed && <span className="font-mono text-sm font-semibold">FAIR-5G</span>}
          <button onClick={() => setCollapsed((c) => !c)} className="text-muted-foreground">
            <ChevronLeft className={`h-4 w-4 transition-transform ${collapsed ? "rotate-180" : ""}`} />
          </button>
        </div>

        <div className="space-y-2 px-3">
          <Button className="w-full" asChild>
            <Link to="/pesquisador/novo">{collapsed ? "+" : "Criar ambiente"}</Link>
          </Button>
          <Button variant="outline" className="w-full justify-start gap-2" asChild>
            <Link to="/pesquisador">
              <LayoutGrid className="h-4 w-4" />
              {!collapsed && "Menu"}
            </Link>
          </Button>
        </div>

        {!collapsed && (
          <nav className="mt-6 flex-1 space-y-6 overflow-y-auto px-3">
            <div>
              <p className="px-2 text-xs font-medium text-muted-foreground">MÓDULOS</p>
              <div className="mt-2 space-y-1">
                <Collapsible defaultOpen>
                  <CollapsibleTrigger className="group flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-muted">
                    <span className="flex items-center gap-2">
                      <Boxes className="h-4 w-4" />
                      Ambientes
                    </span>
                    <ChevronDown className="h-3 w-3 transition-transform duration-200 group-data-[state=open]:rotate-180" />
                  </CollapsibleTrigger>
                  <CollapsibleContent className="ml-6 space-y-1 overflow-hidden border-l pl-3 data-[state=open]:animate-collapsible-down data-[state=closed]:animate-collapsible-up">
                    {AMBIENTES_ITEMS.map((item) => {
                      const active = location.pathname === item.to
                      return (
                        <Link
                          key={item.to}
                          to={item.to}
                          className={`block rounded-md px-2 py-1 text-sm ${
                            active ? "border-l-2 border-[#0633FF] font-medium text-foreground" : "text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {item.label}
                        </Link>
                      )
                    })}
                  </CollapsibleContent>
                </Collapsible>

                <Link
                  to="/pesquisador/monitoramento"
                  className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                    location.pathname === "/pesquisador/monitoramento"
                      ? "font-medium text-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <Activity className="h-4 w-4" />
                  Monitoramento
                </Link>
              </div>
            </div>

            <div>
              <p className="px-2 text-xs font-medium text-muted-foreground">RECURSOS</p>
              <div className="mt-2 space-y-1">
                <Link to="/pesquisador/guia" className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground">
                  <BookOpen className="h-4 w-4" />
                  Guia
                </Link>
              </div>
            </div>
          </nav>
        )}
      </aside>

      <div className="flex-1"><Outlet /></div>
    </div>
  )
}