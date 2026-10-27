import { Outlet, useLocation, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Search, HelpCircle, ChevronDown } from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { CleanupDialog } from '@/components/CleanupDialog'

const MODES = [
  { key: 'pesquisador', labelKey: 'common.modes.researcher', path: '/pesquisador' },
  { key: 'estudante', labelKey: 'common.modes.student', path: '/tutorial' },
] as const

export default function AppShell() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()

  const currentMode = location.pathname.startsWith('/tutorial') ? 'estudante' : 'pesquisador'
  const currentLabelKey = MODES.find((m) => m.key === currentMode)?.labelKey

  return (
    <div className="flex h-screen flex-col">
      <header className="flex shrink-0 items-center justify-end gap-3 border-b px-6 py-3">
        <span className="text-sm text-muted-foreground">
          {t('topbar.currentMode')}<span className="pl-2 pr-2 font-medium text-foreground">{currentLabelKey && t(currentLabelKey)}</span>
        </span>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="gap-1">
              {t('topbar.changeMode')}
              <ChevronDown className="h-3 w-3" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {MODES.map((mode) => (
              <DropdownMenuItem key={mode.key} onClick={() => navigate(mode.path)}>
                {t(mode.labelKey)}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <CleanupDialog />

        <Button variant="ghost" size="icon"><Search className="h-4 w-4" /></Button>
        <Button variant="ghost" size="icon"><HelpCircle className="h-4 w-4" /></Button>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto"><Outlet /></main>
    </div>
  )
}