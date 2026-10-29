import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { ChevronDown, Hash, Info, Search } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { norm } from '@/lib/runs'
import { currentLocale } from '@/i18n'
import type { GuiaContent, GuiaFaq, GuiaSection, GuiaTerm } from '@/content/guia/types'
import { ptBR } from '@/content/guia/pt-BR'
import { en } from '@/content/guia/en'

// laranja do projeto (#F5A623); em texto no tema claro, um tom mais escuro para manter o contraste
const ORANGE_TEXT = 'text-[#B86E00] dark:text-[#F5A623]'

const CONTENT: Record<string, GuiaContent> = { 'pt-BR': ptBR, en }

const TABS = ['primeiros-passos', 'campos', 'glossario', 'faq'] as const
type Tab = (typeof TABS)[number]
const isTab = (v: string | null): v is Tab => (TABS as readonly string[]).includes(v ?? '')

// prefixo da âncora -> aba que contém o item (#faq-x abre o FAQ mesmo sem ?aba=)
const ANCHOR_TAB: [string, Tab][] = [['passo-', 'primeiros-passos'], ['campo-', 'campos'], ['termo-', 'glossario'], ['faq-', 'faq']]
const tabOfAnchor = (id: string) => ANCHOR_TAB.find(([prefix]) => id.startsWith(prefix))?.[1] ?? null

// item alvo da âncora: destacado e focável (foco visível para quem navega por teclado)
const targetClass = (active: boolean) =>
  `scroll-mt-6 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring ${active ? 'ring-2 ring-[#F5A623]/60 bg-[#F5A623]/5' : ''}`

// `trecho` -> <code>
function RichText({ text }: { text: string }) {
  return (
    <>
      {text.split('`').map((part, i) =>
        i % 2 ? <code key={i} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">{part}</code> : <Fragment key={i}>{part}</Fragment>
      )}
    </>
  )
}

function AnchorLink({ tab, id, title }: { tab: Tab; id: string; title: string }) {
  const { t } = useTranslation()
  return (
    <Link
      to={{ search: `?aba=${tab}`, hash: id }}
      replace
      aria-label={t('guide.anchorLink', { title })}
      className="rounded text-muted-foreground opacity-60 hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Hash className="h-3.5 w-3.5" />
    </Link>
  )
}

function Section({ section, tab, anchor, active, index }: { section: GuiaSection; tab: Tab; anchor: string; active: boolean; index?: number }) {
  return (
    <section id={anchor} tabIndex={-1} className={`space-y-2 p-3 ${targetClass(active)}`}>
      <h3 className="flex items-center gap-2 font-medium">
        {index != null && (
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#F5A623] text-xs font-medium text-neutral-950">{index}</span>
        )}
        {section.title}
        <AnchorLink tab={tab} id={anchor} title={section.title} />
      </h3>
      {section.body.map((p, i) => (
        <p key={i} className="leading-relaxed text-muted-foreground"><RichText text={p} /></p>
      ))}
      {section.links && (
        <div className="flex flex-wrap gap-3 pt-1">
          {section.links.map((l) => (
            <Link key={l.to} to={l.to} className={`text-sm font-medium underline-offset-4 hover:underline ${ORANGE_TEXT}`}>{l.label} ›</Link>
          ))}
        </div>
      )}
    </section>
  )
}

const termText = (g: GuiaTerm) => norm([g.term, g.full, g.body, g.where].filter(Boolean).join(' '))
const faqText = (f: GuiaFaq) => norm([f.q, ...f.a].join(' '))

export default function PesquisadorGuia() {
  const { t, i18n } = useTranslation()
  const content = CONTENT[i18n.resolvedLanguage ?? 'pt-BR'] ?? ptBR
  const [searchParams] = useSearchParams()
  const { hash } = useLocation()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [openFaq, setOpenFaq] = useState<Set<string>>(() => new Set())

  const anchor = decodeURIComponent(hash.replace(/^#/, ''))
  const param = searchParams.get('aba')
  // a âncora manda na aba; sem ela, vale o ?aba= (e o padrão é "primeiros passos")
  const tab: Tab = tabOfAnchor(anchor) ?? (isTab(param) ? param : 'primeiros-passos')

  const q = norm(query.trim())
  const glossary = useMemo(() => {
    const locale = currentLocale()
    return [...content.glossary]
      .filter((g) => !q || termText(g).includes(q))
      .sort((a, b) => a.term.localeCompare(b.term, locale, { sensitivity: 'base' }))
  }, [content, q])
  const faq = useMemo(() => content.faq.filter((f) => !q || faqText(f).includes(q)), [content, q])

  // rola até o item da âncora assim que a aba dele estiver montada
  useEffect(() => {
    if (!anchor) return
    const el = document.getElementById(anchor)
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    el.focus({ preventScroll: true })
  }, [anchor, tab])

  function changeTab(value: string) {
    // trocar de aba descarta a âncora, senão ela puxaria de volta para a aba antiga
    if (isTab(value)) navigate({ search: `?aba=${value}`, hash: '' }, { replace: true })
  }

  function toggleFaq(id: string, open: boolean) {
    setOpenFaq((prev) => {
      const next = new Set(prev)
      if (open) next.add(id)
      else next.delete(id)
      return next
    })
    // fechar o item apontado pela âncora: tira a âncora (senão ele continuaria aberto)
    if (!open && anchor === `faq-${id}`) navigate({ search: `?aba=faq`, hash: '' }, { replace: true })
  }

  const counted = (label: string, n: number) => (q ? `${label} (${n})` : label)

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">{t('guide.title')}</h1>
        <p className="text-sm text-muted-foreground">{t('guide.subtitle')}</p>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('guide.search')}
          aria-label={t('guide.search')}
          className="pl-8"
        />
      </div>

      <Tabs value={tab} onValueChange={changeTab} className="gap-4">
        <TabsList className="h-auto flex-wrap">
          <TabsTrigger value="primeiros-passos">{t('guide.tabs.steps')}</TabsTrigger>
          <TabsTrigger value="campos">{t('guide.tabs.fields')}</TabsTrigger>
          <TabsTrigger value="glossario">{counted(t('guide.tabs.glossary'), glossary.length)}</TabsTrigger>
          <TabsTrigger value="faq">{counted(t('guide.tabs.faq'), faq.length)}</TabsTrigger>
        </TabsList>

        <TabsContent value="primeiros-passos" className="space-y-4">
          <div role="note" className="flex items-start gap-3 rounded-lg border border-[#F5A623]/40 bg-[#F5A623]/10 p-4">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-[#F5A623]" />
            <div className="space-y-1">
              <p className="font-medium">{content.steps.notice.title}</p>
              <p className="leading-relaxed text-muted-foreground">{content.steps.notice.body}</p>
            </div>
          </div>
          <Card className="gap-0 px-3 py-3">
            <ol className="space-y-2">
              {content.steps.items.map((s, i) => (
                <li key={s.id}>
                  <Section section={s} tab="primeiros-passos" anchor={`passo-${s.id}`} active={anchor === `passo-${s.id}`} index={i + 1} />
                </li>
              ))}
            </ol>
          </Card>
        </TabsContent>

        <TabsContent value="campos" className="space-y-4">
          <Card className="gap-2 px-3 py-3">
            {content.fields.items.map((s) => (
              <Section key={s.id} section={s} tab="campos" anchor={`campo-${s.id}`} active={anchor === `campo-${s.id}`} />
            ))}
          </Card>
          {[content.fields.example, content.fields.isolation].map((s) => (
            <Card key={s.id} className="gap-0 px-3 py-3">
              <Section section={s} tab="campos" anchor={`campo-${s.id}`} active={anchor === `campo-${s.id}`} />
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="glossario" className="space-y-3">
          <ResultCount query={query} count={glossary.length} />
          {glossary.length > 0 && (
            <Card className="gap-0 divide-y py-0">
              {glossary.map((g) => {
                const id = `termo-${g.id}`
                return (
                  <div key={g.id} id={id} tabIndex={-1} className={`space-y-1 px-4 py-3 ${targetClass(anchor === id)}`}>
                    <h3 className="flex flex-wrap items-baseline gap-x-2">
                      <span className="font-mono font-semibold">{g.term}</span>
                      {g.full && <span className="text-sm text-muted-foreground">{g.full}</span>}
                      <AnchorLink tab="glossario" id={id} title={g.term} />
                    </h3>
                    <p className="leading-relaxed"><RichText text={g.body} /></p>
                    {g.where && (
                      <p className="text-xs text-muted-foreground">
                        <span className="font-medium">{t('guide.where')}</span> {g.where}
                      </p>
                    )}
                  </div>
                )
              })}
            </Card>
          )}
        </TabsContent>

        <TabsContent value="faq" className="space-y-3">
          <ResultCount query={query} count={faq.length} />
          {faq.map((f) => {
            const id = `faq-${f.id}`
            const open = openFaq.has(f.id) || anchor === id
            return (
              <Collapsible key={f.id} open={open} onOpenChange={(o) => toggleFaq(f.id, o)}>
                <Card id={id} tabIndex={-1} className={`gap-0 py-0 ${targetClass(anchor === id)}`}>
                  <div className="flex items-center gap-2 pr-4">
                    <CollapsibleTrigger className="group flex flex-1 items-center justify-between gap-3 rounded-lg px-4 py-3 text-left font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring">
                      <span><RichText text={f.q} /></span>
                      <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180" />
                    </CollapsibleTrigger>
                    <AnchorLink tab="faq" id={id} title={f.q.replaceAll('`', '')} />
                  </div>
                  <CollapsibleContent className="space-y-2 px-4 pb-4">
                    {f.a.map((p, i) => (
                      <p key={i} className="leading-relaxed text-muted-foreground"><RichText text={p} /></p>
                    ))}
                  </CollapsibleContent>
                </Card>
              </Collapsible>
            )
          })}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function ResultCount({ query, count }: { query: string; count: number }) {
  const { t } = useTranslation()
  if (!query.trim()) return null
  return (
    <p role="status" className="text-sm text-muted-foreground">
      {count ? t('guide.results', { count }) : t('guide.noResults', { query: query.trim() })}
    </p>
  )
}
