import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { runBootstrap, streamBootstrapLogs } from "@/lib/api"
import { useBootstrap } from "@/lib/bootstrap-context"

type Phase = "idle" | "running" | "done" | "error"

export default function Bootstrap() {
  const { t } = useTranslation()
  const { status, checking, refresh } = useBootstrap()
  const [phase, setPhase] = useState<Phase>("idle")
  const [logLines, setLogLines] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const stopStreamRef = useRef<(() => void) | undefined>(undefined)
  const logEndRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    return () => stopStreamRef.current?.()
  }, [])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logLines])

  async function handleRun(force: boolean) {
    setError(null)
    setLogLines([])
    try {
      const res = await runBootstrap(force)
      if (res.status === "already_bootstrapped") {
        await refresh()
        return
      }
      setPhase("running")
      stopStreamRef.current = streamBootstrapLogs(
        (line) => setLogLines((prev) => [...prev, line]),
        async () => {
          setPhase("done")
          await refresh() // atualiza o context -> BootstrapGate libera o menu sem reload
        }
      )
    } catch {
      setError(t("bootstrap.startError"))
      setPhase("error")
    }
  }

  const alreadyDone = status?.bootstrapped ?? false

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("bootstrap.title")}</h1>
        <p className="text-muted-foreground">
          {t("bootstrap.subtitle")}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("bootstrap.checklist")}</CardTitle>
          <CardDescription>{t("bootstrap.checklistDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {checking ? (
            <p className="text-sm text-muted-foreground">{t("bootstrap.checking")}</p>
          ) : status ? (
            <>
              <ChecklistItem label="Docker" ok={status.checks.docker} />
              <ChecklistItem label="Mininet (mn)" ok={status.checks.mn} />
              <ChecklistItem label="Containernet/OpenFlow" ok={status.checks.openflow} />
            </>
          ) : (
            <p className="text-sm text-destructive">{t("bootstrap.statusError")}</p>
          )}
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex gap-2">
        <Button onClick={() => handleRun(false)} disabled={phase === "running"}>
          {alreadyDone ? t("bootstrap.runAgain") : t("bootstrap.run")}
        </Button>
        {alreadyDone && (
          <Button variant="outline" onClick={() => handleRun(true)} disabled={phase === "running"}>
            {t("bootstrap.forceReinstall")}
          </Button>
        )}
        {alreadyDone && phase !== "running" && (
          <Button variant="ghost" onClick={() => navigate("/dashboard")}>
            {t("bootstrap.goToMenu")}
          </Button>
        )}
      </div>

      {(phase === "running" || logLines.length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Log</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 overflow-y-auto rounded-md bg-muted p-3 font-mono text-xs">
              {logLines.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
              <div ref={logEndRef} />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function ChecklistItem({ label, ok }: { label: string; ok: boolean }) {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-between text-sm">
      <span>{label}</span>
      <Badge variant={ok ? "default" : "secondary"}>{ok ? "OK" : t("bootstrap.pending")}</Badge>
    </div>
  )
}