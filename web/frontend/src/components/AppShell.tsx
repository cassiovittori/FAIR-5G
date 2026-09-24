import { Outlet, useLocation, useNavigate } from 'react-router'
import { Search, HelpCircle, ChevronDown } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/theme-toggle'

const MODES = [
  { key: 'pesquisador', label: 'Pesquisador', path: '/pesquisador' },
  { key: 'estudante', label: 'Estudante', path: '/tutorial' },
] as const

export default function AppShell() {
  const location = useLocation()
  const navigate = useNavigate()

  const currentMode = location.pathname.startsWith('/tutorial') ? 'estudante' : 'pesquisador'
  const currentLabel = MODES.find((m) => m.key === currentMode)?.label

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-end gap-3 border-b px-6 py-3">
        <span className="text-sm text-muted-foreground">
          Você está no modo:<span className="pl-2 pr-2 font-medium text-foreground">{currentLabel}</span>
        </span>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="gap-1">
              Alterar modo
              <ChevronDown className="h-3 w-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {MODES.map((mode) => (
              <DropdownMenuItem key={mode.key} onClick={() => navigate(mode.path)}>
                {mode.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <Button variant="ghost" size="icon"><Search className="h-4 w-4" /></Button>
        <Button variant="ghost" size="icon"><HelpCircle className="h-4 w-4" /></Button>
        <ThemeToggle />
      </header>

      <main className="flex-1"><Outlet /></main>
    </div>
  )
}