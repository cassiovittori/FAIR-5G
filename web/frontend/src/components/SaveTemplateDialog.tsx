import { useState } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { createPreset, type Preset } from '@/lib/api'

type Config = Record<string, unknown>

interface Props {
  // chamado ao clicar: null = config inválido (quem chama já mostrou o erro) e o diálogo não abre
  getConfig: () => Config | null
  defaultName?: string
  disabled?: boolean
}

// "Salvar como template": usado no formulário de criação e no detalhe do ambiente
export function SaveTemplateDialog({ getConfig, defaultName = '', disabled }: Props) {
  const { t } = useTranslation()
  const [config, setConfig] = useState<Config | null>(null)

  function handleClick() {
    const cfg = getConfig()
    if (cfg) setConfig(cfg)
  }

  return (
    <>
      <Button type="button" variant="outline" onClick={handleClick} disabled={disabled}>
        {t('template.dialog.open')}
      </Button>
      <Dialog open={config != null} onOpenChange={(open) => !open && setConfig(null)}>
        <DialogContent>
          {/* só monta com o diálogo aberto: cada abertura começa com o form limpo */}
          {config && <SaveTemplateForm config={config} defaultName={defaultName} onClose={() => setConfig(null)} />}
        </DialogContent>
      </Dialog>
    </>
  )
}

function SaveTemplateForm({ config, defaultName, onClose }: { config: Config; defaultName: string; onClose: () => void }) {
  const { t } = useTranslation()
  const [nome, setNome] = useState(defaultName)
  const [descricao, setDescricao] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<Preset | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    // eventos do React atravessam o portal: sem isso, o submit chegaria ao form de criação do ambiente
    e.stopPropagation()
    if (!nome.trim()) {
      setError(t('template.dialog.nameRequired'))
      return
    }
    setError(null)
    setSaving(true)
    try {
      setSaved(await createPreset({ tipo: 'template', nome: nome.trim(), descricao: descricao.trim() || null, config }))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('template.dialog.saveError'))
    } finally {
      setSaving(false)
    }
  }

  if (saved) {
    return (
      <>
        <DialogHeader>
          <DialogTitle>{t('template.dialog.title')}</DialogTitle>
        </DialogHeader>
        <p className="flex items-center gap-2 text-sm">
          <CheckCircle2 className="h-4 w-4 text-[#22C55E]" />
          {t('template.dialog.saved', { name: saved.nome })}
        </p>
        <DialogFooter>
          <Button asChild variant="ghost">
            <Link to="/pesquisador/modelos">{t('template.dialog.viewAll')}</Link>
          </Button>
          <Button onClick={onClose}>{t('common.close')}</Button>
        </DialogFooter>
      </>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-4">
      <DialogHeader>
        <DialogTitle>{t('template.dialog.title')}</DialogTitle>
        <DialogDescription>{t('template.dialog.description')}</DialogDescription>
      </DialogHeader>
      <div className="space-y-2">
        <Label htmlFor="template-nome">{t('template.dialog.nameLabel')}</Label>
        <Input
          id="template-nome"
          maxLength={60}
          autoFocus
          placeholder={t('template.dialog.namePlaceholder')}
          value={nome}
          onChange={(e) => setNome(e.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="template-descricao">{t('template.dialog.descriptionLabel')}</Label>
        <Input
          id="template-descricao"
          maxLength={200}
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
        />
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <DialogFooter>
        <Button type="button" variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
        <Button type="submit" disabled={saving}>{saving ? t('template.dialog.saving') : t('template.dialog.save')}</Button>
      </DialogFooter>
    </form>
  )
}
