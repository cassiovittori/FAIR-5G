import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useBlocker, useNavigate, useSearchParams, type BlockerFunction } from 'react-router'
import { Trans, useTranslation } from 'react-i18next'
import { Card, CardContent } from '@/components/ui/card'
import { Info, TriangleAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { SaveTemplateDialog } from '@/components/SaveTemplateDialog'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import {
  ApiError, createPreset, loadErrorMessage, deletePreset, getPreset, getRun, listPresets, startEnvironment, stopEnvironment, updatePreset,
  type Preset, type UpConfig,
} from '@/lib/api'
import { CAMPOS, UES_PER_SLICE, UES_SOFT_WARNING_TOTAL } from '@/lib/up-fields'
import i18n from '@/i18n'

type UesMode = 'all' | 'per-slice'

// abre o Guia em outra aba para não sair do formulário (e não cair no aviso de rascunho)
function LearnMore({ anchor }: { anchor: string }) {
  const { t } = useTranslation()
  return (
    <Link
      to={`/pesquisador/guia?aba=campos#${anchor}`}
      target="_blank"
      rel="noopener"
      className="whitespace-nowrap font-medium text-primary underline-offset-4 hover:underline"
    >
      {t('guide.learnMore')}
    </Link>
  )
}

const isUeCount = (n: number) => Number.isInteger(n) && n >= UES_PER_SLICE.min && n <= UES_PER_SLICE.max

export default function PesquisadorNovo() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const from = searchParams.get('from')
  const templateParam = searchParams.get('template')
  const draftParam = searchParams.get('draft')
  const hasOrigin = Boolean(from || templateParam || draftParam)

  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(CAMPOS.map((c) => [c.nome, String(c.padrao)]))
  )
  const [copiedFrom, setCopiedFrom] = useState<string | null>(null)
  const [fromTemplate, setFromTemplate] = useState<string | null>(null)
  const [templates, setTemplates] = useState<Preset[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState('')
  // rascunho em edição: salvar ao sair atualiza este em vez de criar outro; some ao criar o ambiente
  const [draftId, setDraftId] = useState<number | null>(null)
  const [savingDraft, setSavingDraft] = useState(false)
  // o usuário mexeu no form (carregar run/template/rascunho não conta): sair pergunta se salva rascunho
  const [dirty, setDirty] = useState(false)
  const leavingRef = useRef(false) // ambiente criado: a navegação para o monitoramento não pergunta
  const [submitting, setSubmitting] = useState(false)
  const [stopping, setStopping] = useState(false)
  // 409 do /up: outro ambiente em uso. `context` = estado dele (starting | running | stopping)
  const [conflict, setConflict] = useState<{ message: string; context?: string } | null>(null)
  const [notice, setNotice] = useState<string | null>(null) // informativo, não é erro
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
    setDirty(true)
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
    setDirty(true)
  }

  // preenche o form a partir de um config salvo (run duplicado, template ou rascunho)
  const applyConfig = useCallback((cfg: Record<string, unknown>) => {
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
    } else {
      setUesMode('all')
      setUesAll(String(UES_PER_SLICE.padrao))
      setUesPer([])
    }
  }, [])

  // "Duplicar": preenche o form com a config do ambiente original
  useEffect(() => {
    if (!from) return
    getRun(from)
      .then((run) => {
        // runs antigos não têm config salvo: cai no slice_count (campo "slices")
        applyConfig({ slices: run.slice_count, ...(run.config ?? {}) })
        setCopiedFrom(run.run_id)
        if (run.nome) setNome(i18n.t('novo.copyName', { name: run.nome }))
      })
      .catch((err) => setError(loadErrorMessage(err, i18n.t('novo.loadSourceError'))))
  }, [from, applyConfig])

  // ?template=<id>: só o config; o nome do template não vira nome do ambiente
  useEffect(() => {
    if (from || !templateParam) return
    getPreset(templateParam)
      .then((preset) => {
        if (preset.tipo !== 'template') throw new Error('not a template')
        applyConfig(preset.config)
        setFromTemplate(preset.nome)
      })
      .catch((err) => setError(loadErrorMessage(err, i18n.t('novo.loadTemplateError'))))
  }, [from, templateParam, applyConfig])

  // ?draft=<id>: config + nome do ambiente digitado
  useEffect(() => {
    if (from || templateParam || !draftParam) return
    getPreset(draftParam)
      .then((preset) => {
        if (preset.tipo !== 'rascunho') throw new Error('not a draft')
        applyConfig(preset.config)
        setNome(preset.nome ?? '')
        setDraftId(preset.id)
      })
      .catch((err) => setError(loadErrorMessage(err, i18n.t('novo.loadDraftError'))))
  }, [from, templateParam, draftParam, applyConfig])

  // "Começar de um template": só no form em branco
  useEffect(() => {
    if (hasOrigin) return
    listPresets('template')
      .then(setTemplates)
      .catch(() => {}) // opcional: sem a lista, o form continua funcionando
  }, [hasOrigin])

  // sair pelo app (links, voltar do navegador...): pergunta no diálogo abaixo
  const shouldBlock = useCallback<BlockerFunction>(
    ({ currentLocation, nextLocation }) =>
      dirty && !leavingRef.current &&
      (currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search),
    [dirty]
  )
  const blocker = useBlocker(shouldBlock)

  // fechar a aba / recarregar: o navegador só permite o aviso nativo dele, sem opção de salvar
  useEffect(() => {
    if (!dirty) return
    const onBeforeUnload = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [dirty])

  function chooseTemplate(id: string) {
    const template = templates.find((p) => String(p.id) === id)
    if (!template) return
    setSelectedTemplate(id)
    setError(null)
    applyConfig(template.config)
    setFromTemplate(template.nome)
  }

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
    setConflict(null)
    setNotice(null)

    const config = buildConfig()
    if (!config) return

    setSubmitting(true)
    try {
      await startEnvironment(config, nome.trim() || undefined)
      // o rascunho virou ambiente; se não der para apagar, fica na lista de modelos
      if (draftId != null) deletePreset(draftId).catch(() => {})
      leavingRef.current = true
      navigate('/pesquisador/monitoramento')
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const context = typeof err.params?.context === 'string' ? err.params.context : undefined
        setConflict({ message: err.message, context })
      } else {
        setError(err instanceof Error ? err.message : t('novo.createError'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  // true = salvo; erro (inclusive config inválido) fica em `error`, mostrado também no diálogo de saída
  async function saveDraft(): Promise<boolean> {
    setError(null)
    const config = buildConfig()
    if (!config) return false

    const body = { nome: nome.trim() || null, config }
    setSavingDraft(true)
    try {
      let draft: Preset
      if (draftId == null) {
        draft = await createPreset({ tipo: 'rascunho', ...body })
      } else {
        try {
          draft = await updatePreset(draftId, body)
        } catch (err) {
          // apagado em outra aba (ou já virou ambiente): salva como um novo
          if (!(err instanceof ApiError && err.status === 404)) throw err
          draft = await createPreset({ tipo: 'rascunho', ...body })
        }
      }
      setDraftId(draft.id)
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : t('novo.saveDraftError'))
      return false
    } finally {
      setSavingDraft(false)
    }
  }

  async function saveDraftAndLeave() {
    if (await saveDraft()) blocker.proceed?.()
  }

  async function handleStop() {
    setStopping(true)
    try {
      await stopEnvironment()
      setConflict(null)
      setNotice(t('novo.stoppingNotice'))
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
        {fromTemplate && (
          <p className="text-xs text-muted-foreground">
            <Trans i18nKey="novo.fromTemplate" values={{ name: fromTemplate }} components={{ b: <span className="font-medium text-foreground" /> }} />
          </p>
        )}
        {draftId != null && <p className="text-xs text-muted-foreground">{t('novo.fromDraft')}</p>}
      </div>

      {!hasOrigin && templates.length > 0 && (
        <div className="space-y-2">
          <Label htmlFor="start-from-template">{t('novo.startFromTemplate')}</Label>
          <Select value={selectedTemplate} onValueChange={chooseTemplate}>
            <SelectTrigger id="start-from-template" className="w-full">
              <SelectValue placeholder={t('novo.startFromTemplatePlaceholder')} />
            </SelectTrigger>
            {/* popper: abre abaixo do campo (o padrão item-aligned põe a opção por cima do trigger) */}
            <SelectContent position="popper" align="start">
              {templates.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.nome}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
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
                    onChange={(e) => {
                      setNome(e.target.value)
                      setDirty(true)
                    }}
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
                  onChange={(e) => {
                    setValues((v) => ({ ...v, [c.nome]: e.target.value }))
                    setDirty(true)
                  }}
                />
                <p className="text-xs text-muted-foreground">
                  {t(c.descricaoKey)} {t('novo.fieldRange', { min: c.min, max: c.max, default: c.padrao })}{' '}
                  <LearnMore anchor={`campo-${c.nome}`} />
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
                  onChange={(e) => {
                    setUesAll(e.target.value)
                    setDirty(true)
                  }}
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

              <p className="text-xs text-muted-foreground">
                {t('novo.ues.description')} <LearnMore anchor="campo-ues" />
              </p>
              {totalUes != null && (
                <p className="text-sm">
                  {t('novo.ues.total', { count: totalUes })}
                  {totalUes > UES_SOFT_WARNING_TOTAL && (
                    <span className="ml-2 text-xs text-[#F5A623]">{t('novo.ues.softWarning')}</span>
                  )}
                </p>
              )}
            </div>

            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            {notice && (
              <p role="status" className="flex items-start gap-2 text-sm text-muted-foreground">
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                {notice}
              </p>
            )}
            {/* junto dos botões: é ali que o usuário está olhando quando clica em "Criar" */}
            {conflict && (
              <div role="alert" className="space-y-3 rounded-lg border border-[#F5A623]/50 bg-[#F5A623]/10 p-3 text-sm">
                <p className="flex items-start gap-2">
                  <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-[#F5A623]" />
                  <span className="font-medium">{conflict.message}</span>
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button asChild size="sm" variant="outline">
                    <Link to="/pesquisador/monitoramento">
                      {conflict.context === 'running' ? t('novo.viewEnvironment') : t('common.follow')}
                    </Link>
                  </Button>
                  {/* só dá para parar um ambiente ativo; subindo ou encerrando, o backend recusa */}
                  {(conflict.context === 'running' || conflict.context == null) && (
                    <Button type="button" size="sm" variant="outline" onClick={handleStop} disabled={stopping}>
                      {stopping ? t('common.stopping') : t('common.stop')}
                    </Button>
                  )}
                </div>
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2">
              <SaveTemplateDialog
                getConfig={() => {
                  setError(null)
                  return buildConfig()
                }}
                defaultName={nome.trim()}
                disabled={submitting}
              />
              <div className="flex gap-2">
                <Button asChild variant="ghost">
                  <Link to="/pesquisador">{t('common.cancel')}</Link>
                </Button>
                <Button type="submit" disabled={submitting}>
                  {submitting ? t('novo.creating') : t('common.createEnvironment')}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </form>

      <Dialog open={blocker.state === 'blocked'} onOpenChange={(open) => !open && !savingDraft && blocker.reset?.()}>
        <DialogContent showCloseButton={!savingDraft}>
          <DialogHeader>
            <DialogTitle>{t('novo.leave.title')}</DialogTitle>
            <DialogDescription>{t('novo.leave.description')}</DialogDescription>
          </DialogHeader>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button variant="ghost" onClick={() => blocker.reset?.()} disabled={savingDraft}>{t('novo.leave.stay')}</Button>
            <Button variant="outline" onClick={() => blocker.proceed?.()} disabled={savingDraft}>{t('novo.leave.discard')}</Button>
            <Button onClick={saveDraftAndLeave} disabled={savingDraft}>
              {savingDraft ? t('novo.savingDraft') : t('novo.leave.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}