import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Trans, useTranslation } from 'react-i18next'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, getRun, startEnvironment, stopEnvironment, type UpConfig } from '@/lib/api'
import { CAMPOS, UES_PER_SLICE, UES_SOFT_WARNING_TOTAL } from '@/lib/up-fields'
import i18n from '@/i18n'

type UesMode = 'all' | 'per-slice'

const isUeCount = (n: number) => Number.isInteger(n) && n >= UES_PER_SLICE.min && n <= UES_PER_SLICE.max

export default function PesquisadorNovo() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const from = searchParams.get('from')

  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(CAMPOS.map((c) => [c.nome, String(c.padrao)]))
  )
  const [copiedFrom, setCopiedFrom] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [nome, setNome] = useState<string>('')
  const [uesMode, setUesMode] = useState<UesMode>('all')
  const [uesAll, setUesAll] = useState(String(UES_PER_SLICE.padrao))
  // pode ficar maior/menor que o nº de fatias: a UI lê só as N primeiras (uesPerSlice abaixo),
  // então reduzir e voltar a aumentar as fatias preserva o que foi digitado
  const [uesPer, setUesPer] = useState<string[]>([])

  const slicesCampo = CAMPOS.find((c) => c.nome === 'slices')
  const sliceCountRaw = Number(values.slices)
  const sliceCount =
    slicesCampo && Number.isInteger(sliceCountRaw) && sliceCountRaw >= slicesCampo.min && sliceCountRaw <= slicesCampo.max
      ? sliceCountRaw
      : 0 // inválido enquanto digita: esconde os campos por fatia e o total
  const uesPerSlice = Array.from({ length: sliceCount }, (_, i) => uesPer[i] ?? String(UES_PER_SLICE.padrao))
  const uesList = uesMode === 'all' ? Array<string>(sliceCount).fill(uesAll) : uesPerSlice
  const uesNumbers = uesList.map(Number)
  const totalUes = sliceCount > 0 && uesNumbers.every(isUeCount) ? uesNumbers.reduce((a, b) => a + b, 0) : null

  function setUePer(index: number, value: string) {
    setUesPer((prev) => {
      const next = Array.from({ length: Math.max(prev.length, sliceCount) }, (_, i) => prev[i] ?? String(UES_PER_SLICE.padrao))
      next[index] = value
      return next
    })
  }

  function changeUesMode(mode: UesMode) {
    // ao passar para "por fatia", parte do valor único em todas
    if (mode === 'per-slice' && uesMode === 'all') setUesPer(Array<string>(sliceCount).fill(uesAll))
    setUesMode(mode)
  }

  // "Duplicar": preenche o form com a config do ambiente original
  useEffect(() => {
    if (!from) return
    getRun(from)
      .then((run) => {
        // runs antigos não têm config salvo: cai no slice_count (campo "slices")
        const cfg: Record<string, unknown> = { slices: run.slice_count, ...(run.config ?? {}) }
        setValues((prev) => {
          const next = { ...prev }
          for (const c of CAMPOS) {
            const v = cfg[c.nome]
            if (typeof v === 'number' && v >= c.min && v <= c.max) next[c.nome] = String(v)
          }
          return next
        })
        // UEs: só aproveita se for uma lista válida com uma entrada por fatia; runs antigos -> padrão (1)
        const ues = cfg.ues_per_slice
        if (
          Array.isArray(ues) && ues.length === cfg.slices &&
          ues.every((n) => typeof n === 'number' && isUeCount(n))
        ) {
          const allSame = ues.every((n) => n === ues[0])
          setUesMode(allSame ? 'all' : 'per-slice')
          setUesAll(String(ues[0]))
          setUesPer(ues.map(String))
        }
        setCopiedFrom(run.run_id)
        if (run.nome) setNome(i18n.t('novo.copyName', { name: run.nome }))
      })
      .catch(() => setError(i18n.t('novo.loadSourceError')))
  }, [from])

  function buildConfig(): UpConfig | null {
    const config: UpConfig = {}
    for (const c of CAMPOS) {
      const n = Number(values[c.nome])
      if (!Number.isInteger(n) || n < c.min || n > c.max) {
        setError(t('novo.invalidField', { field: t(c.labelKey), min: c.min, max: c.max }))
        return null
      }
      config[c.nome] = n
    }
    // sempre como lista (uma entrada por fatia); o backend revalida com o upstream
    for (const [i, raw] of uesList.entries()) {
      const n = Number(raw)
      if (!isUeCount(n)) {
        const field = uesMode === 'all' ? t('novo.ues.label') : t('novo.ues.sliceField', { id: i + 1 })
        setError(t('novo.invalidField', { field, min: UES_PER_SLICE.min, max: UES_PER_SLICE.max }))
        return null
      }
    }
    config.ues_per_slice = uesList.map(Number)
    return config
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setConflict(false)

    const config = buildConfig()
    if (!config) return

    setSubmitting(true)
    try {
      await startEnvironment(config, nome.trim() || undefined)
      navigate('/pesquisador/monitoramento')
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConflict(true)
      } else {
        setError(err instanceof Error ? err.message : t('novo.createError'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  async function handleStop() {
    setStopping(true)
    try {
      await stopEnvironment()
      setConflict(false)
      setError(t('novo.stoppingNotice'))
    } catch(err) {
      setError(err instanceof Error ? err.message : t('common.stopError'))
    } finally {
      setStopping(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">{t('common.createEnvironment')}</h1>
        <p className="text-sm text-muted-foreground">
          {t('novo.subtitle')}
        </p>
        {copiedFrom && (
          <p className="text-xs text-muted-foreground">
            <Trans i18nKey="novo.copiedFrom" values={{ runId: copiedFrom }} components={{ mono: <span className="font-mono" /> }} />
          </p>
        )}
      </div>

      {conflict && (
        <Card className="border-[#F5A623]">
          <CardHeader>
            <CardTitle className="text-sm">{t('novo.conflictTitle')}</CardTitle>
            <CardDescription>
              {t('novo.conflictDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex gap-2">
            <Button asChild variant="outline" className="flex-1">
              <Link to="/pesquisador/monitoramento">{t('novo.viewEnvironment')}</Link>
            </Button>
            <Button variant="outline" className="flex-1" onClick={handleStop} disabled={stopping}>
              {stopping ? t('common.stopping') : t('common.stop')}
            </Button>
          </CardContent>
        </Card>
      )}

      <form onSubmit={handleSubmit}>
        <Card>
          <CardContent className="space-y-6 pt-6">
            <div className="space-y-2">
                <Label htmlFor="nome">{t('novo.nameLabel')}</Label>
                <Input
                    id="nome"
                    maxLength={60}
                    placeholder={t('novo.namePlaceholder')}
                    value={nome}
                    onChange={(e) => setNome(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                    {t('novo.nameHint')}
                </p>
            </div>
            {CAMPOS.map((c) => (
              <div key={c.nome} className="space-y-2">
                <Label htmlFor={c.nome}>{t(c.labelKey)}</Label>
                <Input
                  id={c.nome}
                  type="number"
                  min={c.min}
                  max={c.max}
                  value={values[c.nome]}
                  onChange={(e) => setValues((v) => ({ ...v, [c.nome]: e.target.value }))}
                />
                <p className="text-xs text-muted-foreground">
                  {t(c.descricaoKey)} {t('novo.fieldRange', { min: c.min, max: c.max, default: c.padrao })}
                </p>
              </div>
            ))}

            <div className="space-y-2">
              <Label htmlFor={uesMode === 'all' ? 'ues-all' : undefined}>{t('novo.ues.label')}</Label>
              <div className="flex gap-2">
                {(['all', 'per-slice'] as const).map((mode) => (
                  <Button
                    key={mode}
                    type="button"
                    size="sm"
                    variant={uesMode === mode ? 'secondary' : 'outline'}
                    aria-pressed={uesMode === mode}
                    onClick={() => changeUesMode(mode)}
                  >
                    {mode === 'all' ? t('novo.ues.modeAll') : t('novo.ues.modePerSlice')}
                  </Button>
                ))}
              </div>

              {uesMode === 'all' ? (
                <Input
                  id="ues-all"
                  type="number"
                  min={UES_PER_SLICE.min}
                  max={UES_PER_SLICE.max}
                  value={uesAll}
                  onChange={(e) => setUesAll(e.target.value)}
                />
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {uesPerSlice.map((v, i) => (
                    <div key={i} className="space-y-1">
                      <Label htmlFor={`ues-${i + 1}`} className="text-xs text-muted-foreground">{t('common.sliceN', { id: i + 1 })}</Label>
                      <Input
                        id={`ues-${i + 1}`}
                        type="number"
                        min={UES_PER_SLICE.min}
                        max={UES_PER_SLICE.max}
                        value={v}
                        onChange={(e) => setUePer(i, e.target.value)}
                      />
                    </div>
                  ))}
                </div>
              )}

              <p className="text-xs text-muted-foreground">{t('novo.ues.description')}</p>
              {totalUes != null && (
                <p className="text-sm">
                  {t('novo.ues.total', { count: totalUes })}
                  {totalUes > UES_SOFT_WARNING_TOTAL && (
                    <span className="ml-2 text-xs text-[#F5A623]">{t('novo.ues.softWarning')}</span>
                  )}
                </p>
              )}
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

            <div className="flex justify-end gap-2">
              <Button asChild variant="ghost">
                <Link to="/pesquisador">{t('common.cancel')}</Link>
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? t('novo.creating') : t('common.createEnvironment')}
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  )
}