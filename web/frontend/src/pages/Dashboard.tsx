import { useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/lib/auth'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export default function Dashboard() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{t('modo.greeting', { email: user?.email })}</h1>
          <p className="text-muted-foreground">{t('modo.subtitle')}</p>
        </div>
        <Button variant="ghost" onClick={logout}>{t('modo.logout')}</Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <ModeCard
          title={t('common.modes.researcher')}
          description={t('modo.researcherDescription')}
          accent="pesquisador"
          highlighted={user?.role === 'pesquisador'}
          onSelect={() => navigate('/pesquisador')}
        />
        <ModeCard
          title={t('common.modes.student')}
          description={t('modo.studentDescription')}
          accent="estudante"
          highlighted={user?.role === 'estudante'}
          onSelect={() => navigate('/tutorial')}
        />
      </div>
    </div>
  )
}

function ModeCard({
  title,
  description,
  accent,
  highlighted,
  onSelect,
}: {
  title: string
  description: string
  accent: 'pesquisador' | 'estudante'
  highlighted: boolean
  onSelect: () => void
}) {
  const { t } = useTranslation()
  const color = accent === 'pesquisador' ? '#0633FF' : '#8B5CF6'

  return (
    <Card
      className="transition-colors"
      style={highlighted ? { borderColor: color } : undefined}
    >
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle>{title}</CardTitle>
          {highlighted && (
            <span
              className="rounded-full px-2 py-0.5 text-xs"
              style={{ color, backgroundColor: `${color}1A` }}
            >
              {t('modo.yourProfile')}
            </span>
          )}
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button className="w-full" onClick={onSelect} variant={highlighted ? 'default' : 'outline'}>
          {t('modo.enterMode', { mode: title })}
        </Button>
      </CardContent>
    </Card>
  )
}