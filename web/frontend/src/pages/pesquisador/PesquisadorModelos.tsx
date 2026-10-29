import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { deletePreset, listPresets, updatePreset, type Preset, type PresetTipo } from '@/lib/api'
import { configSummary, fmtDateTime } from '@/lib/runs'
import i18n from '@/i18n'

const presetLabel = (p: Preset) => p.nome?.trim() || i18n.t('modelos.untitledDraft')

export default function PesquisadorModelos() {
  const { t } = useTranslation()
  const [presets, setPresets] = useState<Preset[] | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [toDelete, setToDelete] = useState<Preset | null>(null)

  useEffect(() => {
    listPresets()
      .then(setPresets)
      .catch(() => setLoadError(true))
  }, [])

  // a lista vem por updated_at desc: o item editado sobe para o topo, como no backend
  const replace = (p: Preset) => setPresets((prev) => prev && [p, ...prev.filter((x) => x.id !== p.id)])
  const remove = (id: number) => setPresets((prev) => prev && prev.filter((x) => x.id !== id))

  const sections: { tipo: PresetTipo; title: string; empty: string }[] = [
    { tipo: 'template', title: t('modelos.templates'), empty: t('modelos.templatesEmpty') },
    { tipo: 'rascunho', title: t('modelos.drafts'), empty: t('modelos.draftsEmpty') },
  ]

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{t('modelos.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('modelos.subtitle')}</p>
        </div>
        <Button asChild><Link to="/pesquisador/novo">{t('common.createEnvironment')}</Link></Button>
      </div>

      {loadError && <p className="text-sm text-destructive">{t('modelos.loadError')}</p>}

      {sections.map((section) => {
        const items = presets?.filter((p) => p.tipo === section.tipo) ?? []
        return (
          <section key={section.tipo} className="space-y-3">
            <h2 className="text-xs font-medium tracking-wide text-muted-foreground">{section.title}</h2>
            {presets == null && !loadError ? (
              <Skeleton className="h-20" />
            ) : items.length === 0 ? (
              <Card className="px-6 py-4 text-sm text-muted-foreground">{section.empty}</Card>
            ) : (
              <Card className="gap-0 divide-y py-0">
                {items.map((p) => (
                  <PresetRow key={p.id} preset={p} onUpdated={replace} onDelete={() => setToDelete(p)} />
                ))}
              </Card>
            )}
          </section>
        )
      })}

      <Dialog open={toDelete != null} onOpenChange={(open) => !open && setToDelete(null)}>
        <DialogContent>
          {toDelete && (
            <DeleteConfirm
              preset={toDelete}
              onClose={() => setToDelete(null)}
              onDeleted={() => {
                remove(toDelete.id)
                setToDelete(null)
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function PresetRow({ preset, onUpdated, onDelete }: { preset: Preset; onUpdated: (p: Preset) => void; onDelete: () => void }) {
  const { t } = useTranslation()
  const [renaming, setRenaming] = useState(false)
  const [nome, setNome] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isTemplate = preset.tipo === 'template'
  const useHref = `/pesquisador/novo?${isTemplate ? 'template' : 'draft'}=${preset.id}`

  function startRename() {
    setNome(preset.nome ?? '')
    setError(null)
    setRenaming(true)
  }

  async function handleRename(e: React.FormEvent) {
    e.preventDefault()
    if (!nome.trim()) {
      setError(t('template.dialog.nameRequired'))
      return
    }
    setSaving(true)
    setError(null)
    try {
      onUpdated(await updatePreset(preset.id, { nome: nome.trim() }))
      setRenaming(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('modelos.renameError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-3 text-sm">
      <div className="min-w-0 flex-1 space-y-1">
        {renaming ? (
          <form onSubmit={handleRename} className="flex items-center gap-2">
            <Input
              aria-label={t('template.dialog.nameLabel')}
              maxLength={60}
              autoFocus
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              onKeyDown={(e) => e.key === 'Escape' && setRenaming(false)}
              className="h-8 max-w-xs"
            />
            <Button type="submit" size="sm" disabled={saving}>{t('modelos.actions.save')}</Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setRenaming(false)}>{t('common.cancel')}</Button>
          </form>
        ) : (
          <p className="truncate font-medium">{presetLabel(preset)}</p>
        )}
        {error && <p className="text-xs text-destructive">{error}</p>}
        {preset.descricao && <p className="text-xs text-muted-foreground">{preset.descricao}</p>}
        <p className="text-xs text-muted-foreground">
          <span className="font-mono">{configSummary(preset.config)}</span>
          {' · '}
          {t('modelos.updatedAt', { date: fmtDateTime(preset.updated_at) })}
        </p>
      </div>
      <div className="flex gap-2">
        <Button asChild size="sm">
          <Link to={useHref}>{isTemplate ? t('modelos.actions.use') : t('modelos.actions.continue')}</Link>
        </Button>
        {isTemplate && !renaming && (
          <Button size="sm" variant="outline" onClick={startRename}>{t('modelos.actions.rename')}</Button>
        )}
        <Button size="sm" variant="outline" className="hover:border-destructive hover:text-destructive" onClick={onDelete}>
          {t('modelos.actions.delete')}
        </Button>
      </div>
    </div>
  )
}

function DeleteConfirm({ preset, onClose, onDeleted }: { preset: Preset; onClose: () => void; onDeleted: () => void }) {
  const { t } = useTranslation()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    setDeleting(true)
    setError(null)
    try {
      await deletePreset(preset.id)
      onDeleted()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('modelos.deleteError'))
      setDeleting(false)
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {preset.tipo === 'template' ? t('modelos.confirmDelete.titleTemplate') : t('modelos.confirmDelete.titleDraft')}
        </DialogTitle>
        <DialogDescription>{t('modelos.confirmDelete.description', { name: presetLabel(preset) })}</DialogDescription>
      </DialogHeader>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
        <Button variant="destructive" onClick={handleConfirm} disabled={deleting}>
          {deleting ? t('modelos.confirmDelete.deleting') : t('modelos.confirmDelete.confirm')}
        </Button>
      </DialogFooter>
    </>
  )
}
