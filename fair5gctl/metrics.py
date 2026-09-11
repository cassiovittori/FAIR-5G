#!/usr/bin/env python3
"""
metrics.py — Módulo de métricas do FAIR-5G
Funcionalidades:
  - snapshot : consulta métricas atuais do Prometheus
  - watch    : monitoramento em tempo real no terminal
  - report   : gera relatório JSON de uma run
  - grafana  : abre o dashboard no browser
"""

import json
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── dependências opcionais ────────────────────────────────────────────────────
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich import box
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False
    console = None

# ── configuração padrão ───────────────────────────────────────────────────────
PROMETHEUS_URL  = os.environ.get("PROMETHEUS_URL",  "http://localhost:9090")
GRAFANA_URL     = os.environ.get("GRAFANA_URL",     "http://localhost:3000")
GRAFANA_DASHBOARD = os.environ.get("GRAFANA_DASHBOARD", "")

# Derivado de core.slicing (fonte unica de verdade do enderecamento) em vez de
# hardcoded: quando a subnet dos UEs muda, as queries acompanham sozinhas.
def _ue_ip_defaults() -> dict:
    """IPs de acesso dos UEs, por indice de fatia.

    A quantidade de fatias e resolvida nesta ordem de precedencia:
      1. FAIR5G_SLICE_COUNT no ambiente (util para sobrescrever pontualmente);
      2. .fair5g_state.json, gravado pelo `up` — necessario porque `metrics`
         normalmente roda em OUTRO terminal, onde a variavel de ambiente do
         processo do `up` nao existe;
      3. DEFAULT_SLICE_COUNT.

    Sem o passo 2 o painel exibia apenas as fatias padrao mesmo com N no ar
    (observado em 2026-09-09: 4 fatias ativas, 2 exibidas).
    """
    try:
        from .core.slicing import build_slice_specs, DEFAULT_SLICE_COUNT

        count = os.environ.get("FAIR5G_SLICE_COUNT")
        if not count:
            try:
                state_file = Path(__file__).resolve().parent.parent / ".fair5g_state.json"
                count = json.loads(state_file.read_text()).get("slice_count")
            except Exception:
                count = None
        if not count:
            count = DEFAULT_SLICE_COUNT
        return {s.index: s.ue_mininet_ip for s in build_slice_specs(int(count))}
    except Exception:
        return {}


_UE_IPS = _ue_ip_defaults()
UE1_IP = os.environ.get("UE1_IP", _UE_IPS.get(1, ""))
UE2_IP = os.environ.get("UE2_IP", _UE_IPS.get(2, ""))


def _slice_indices() -> list:
    """Indices de fatia ativos, derivados de core.slicing.

    Sem isso as consultas ficariam presas a duas fatias, enquanto o
    prometheus.yml ja e gerado dinamicamente para N fatias: o ambiente
    coletaria tudo e a CLI exibiria apenas metade.
    """
    if _UE_IPS:
        return sorted(_UE_IPS.keys())
    return [1, 2]


def _build_queries() -> dict:
    """Monta as consultas Prometheus para as N fatias ativas.

    NOTA SOBRE A METRICA DE LATENCIA (decisao de 2026-09-09):
    a metrica oficial de latencia e `probe_icmp_duration_seconds{phase="rtt"}`,
    que corresponde ao round-trip time do pacote ICMP.

    A metrica `probe_duration_seconds` foi REMOVIDA do painel. Ela mede a
    duracao total da sondagem do ponto de vista do blackbox exporter, somando
    as fases de resolucao de nome, preparacao do socket e o RTT propriamente
    dito. Ou seja, agrega o custo da instrumentacao ao desempenho da rede, o
    que a torna inadequada como indicador de latencia de rede: e sempre maior
    que o RTT e a diferenca nao tem significado de rede. Exibi-la ao lado do
    RTT convidava a interpretacao equivocada de que seriam duas medidas
    comparaveis da mesma grandeza.
    """
    indices = _slice_indices()

    conectividade = {}
    latencia = {}
    for i in indices:
        ip = _UE_IPS.get(i, "")
        conectividade[f"Probe fatia {i} (OK=1)"] = (
            f'probe_success{{job="blackbox-ping-slices", instance="{ip}"}}'
        )
        latencia[f"Fatia {i} RTT ICMP"] = (
            f'probe_icmp_duration_seconds{{job="blackbox-ping-slices", '
            f'instance="{ip}", phase="rtt"}} * 1000'
        )

    smf = {}
    upf = {}
    for i in indices:
        smf[f"PDU Sessions SMF{i}"] = (
            f'fivegs_smffunction_sm_pdusessioncreationreq'
            f'{{job="smf", instance="smf{i}.open5gs.org:9090"}}'
        )
        upf[f"Sessoes UPF{i}"] = (
            f'fivegs_upffunction_upf_sessionnbr'
            f'{{job="upf", instance="upf{i}.open5gs.org:9090"}}'
        )
        upf[f"QoS Flows UPF{i}"] = (
            f'fivegs_upffunction_upf_qosflows'
            f'{{job="upf", instance="upf{i}.open5gs.org:9090"}}'
        )
        upf[f"GTP Ingress UPF{i} (p/s)"] = (
            f'rate(fivegs_ep_n3_gtp_indatapktn3upf'
            f'{{job="upf", instance="upf{i}.open5gs.org:9090"}}[1m])'
        )

    # Recursos por container (cAdvisor).
    #
    # A separacao entre COMPARTILHADOS e POR FATIA nao e cosmetica: os
    # componentes compartilhados (gNB, AMF, ONOS) sao o caminho pelo qual um
    # efeito atravessa de uma fatia para outra — se sobrecarregar a fatia 1
    # satura a CPU do gNB, a fatia 2 degrada por consequencia, e isso e
    # justamente o mecanismo de falha de isolamento sob investigacao. Os
    # componentes por fatia servem de verificacao: confirmam que a perturbacao
    # chegou onde se pretendia e permitem medir o efeito localizado.
    recursos_compartilhados = {}
    for nome in ("gnb", "amf", "onos-controller"):
        recursos_compartilhados[f"CPU {nome} (%)"] = (
            f'fair5g_container_cpu_percent{{name="{nome}"}}'
        )
        recursos_compartilhados[f"Mem {nome} (MiB)"] = (
            f'fair5g_container_memory_bytes{{name="{nome}"}} / 1024 / 1024'
        )

    recursos_fatia = {}
    for i in indices:
        for nf in (f"upf{i}", f"smf{i}"):
            recursos_fatia[f"CPU {nf} (%)"] = (
                f'fair5g_container_cpu_percent{{name="{nf}"}}'
            )
        recursos_fatia[f"Mem upf{i} (MiB)"] = (
            f'fair5g_container_memory_bytes{{name="upf{i}"}} / 1024 / 1024'
        )

    return {
        "Conectividade": conectividade,
        "Latencia (ms)": latencia,
        "AMF": {
            "UEs Registrados":     'ran_ue{job="amf"}',
            "Sessoes AMF":         'amf_session{job="amf"}',
            "Taxa Registro (r/s)": 'rate(fivegs_amffunction_rm_reginitreq{job="amf"}[1m])',
            "Taxa Auth (r/s)":     'rate(fivegs_amffunction_amf_authreq{job="amf"}[1m])',
        },
        "SMF": smf,
        "UPF": upf,
        "Recursos (compartilhados)": recursos_compartilhados,
        "Recursos (por fatia)": recursos_fatia,
    }


# Queries Prometheus organizadas por categoria
QUERIES = _build_queries()

# ── helpers ───────────────────────────────────────────────────────────────────

def _check_requests():
    if not HAS_REQUESTS:
        _print("[ERRO] Pacote 'requests' não encontrado. Instale: pip install requests")
        raise SystemExit(1)


def _print(msg: str):
    if HAS_RICH:
        console.print(msg)
    else:
        print(msg)


def _query_prometheus(query: str) -> Optional[float]:
    """Executa uma query instant no Prometheus e retorna o valor como float."""
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5,
        )
        data = resp.json()
        results = data.get("data", {}).get("result", [])
        if results:
            return float(results[0]["value"][1])
        return None
    except Exception:
        return None


def _format_value(metric_name: str, value: Optional[float]) -> str:
    """Formata o valor de acordo com o tipo de métrica."""
    if value is None:
        return "N/A"
    if "Probe" in metric_name:
        return "OK" if value == 1.0 else "FALHOU"
    if "(%)" in metric_name:
        return f"{value:.1f} %"
    if "(MiB)" in metric_name:
        return f"{value:.0f} MiB"
    if "ms" in metric_name or "Latencia" in metric_name or "RTT" in metric_name:
        return f"{value:.2f} ms"
    if "r/s" in metric_name or "p/s" in metric_name:
        return f"{value:.4f}/s"
    return f"{value:.2f}"


def _color_value(metric_name: str, value: Optional[float]) -> str:
    """Retorna valor com cor rich para exibição."""
    if value is None:
        return "[dim]N/A[/dim]"
    formatted = _format_value(metric_name, value)
    if "Probe" in metric_name:
        return f"[green]{formatted}[/green]" if value == 1.0 else f"[red]{formatted}[/red]"
    if ("Latencia" in metric_name or "RTT" in metric_name) and value is not None:
        if value > 300:
            return f"[red]{formatted}[/red]"
        if value > 100:
            return f"[yellow]{formatted}[/yellow]"
        return f"[green]{formatted}[/green]"
    return formatted


def _collect_all() -> dict:
    """Coleta todas as métricas e retorna como dict."""
    result = {}
    for category, queries in QUERIES.items():
        result[category] = {}
        for name, query in queries.items():
            result[category][name] = _query_prometheus(query)
    return result


def _build_rich_table(data: dict) -> "Table":
    """Monta tabela rich com os dados coletados."""
    table = Table(
        title=f"Métricas FAIR-5G — {datetime.now().strftime('%H:%M:%S')}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Categoria", style="bold", width=12)
    table.add_column("Métrica", width=28)
    table.add_column("Valor", justify="right", width=20)

    for category, metrics in data.items():
        first = True
        for name, value in metrics.items():
            cat_label = f"[cyan]{category}[/cyan]" if first else ""
            first = False
            val_str = _color_value(name, value) if HAS_RICH else _format_value(name, value)
            table.add_row(cat_label, name, val_str)
        table.add_section()

    return table


def _build_plain_text(data: dict) -> str:
    """Monta texto simples com os dados coletados (fallback sem rich)."""
    lines = [f"=== Métricas FAIR-5G — {datetime.now().strftime('%H:%M:%S')} ==="]
    for category, metrics in data.items():
        lines.append(f"\n[{category}]")
        for name, value in metrics.items():
            lines.append(f"  {name:<35} {_format_value(name, value)}")
    return "\n".join(lines)


# ── comandos públicos ─────────────────────────────────────────────────────────

def cmd_snapshot():
    """Exibe um snapshot único das métricas atuais."""
    _check_requests()
    _print("[bold cyan]Coletando métricas...[/bold cyan]" if HAS_RICH else "Coletando métricas...")

    data = _collect_all()

    if HAS_RICH:
        console.print(_build_rich_table(data))
    else:
        print(_build_plain_text(data))


def cmd_watch(interval: int = 5):
    """Monitoramento em tempo real com refresh a cada `interval` segundos."""
    _check_requests()

    if HAS_RICH:
        _print(f"[dim]Monitorando métricas (refresh: {interval}s) — Ctrl+C para sair[/dim]")
        try:
            with Live(console=console, refresh_per_second=1, screen=True) as live:
                while True:
                    data = _collect_all()
                    table = _build_rich_table(data)
                    panel = Panel(
                        table,
                        title="[bold cyan]FAIR-5G — Monitor em Tempo Real[/bold cyan]",
                        subtitle=f"[dim]refresh: {interval}s — Ctrl+C para sair[/dim]",
                        border_style="cyan",
                    )
                    live.update(panel)
                    time.sleep(interval)
        except KeyboardInterrupt:
            _print("\n[yellow]Monitor encerrado.[/yellow]")
    else:
        print(f"Monitorando métricas (refresh: {interval}s) — Ctrl+C para sair")
        try:
            while True:
                os.system("clear")
                data = _collect_all()
                print(_build_plain_text(data))
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nMonitor encerrado.")


def cmd_report(run_id: str, runs_dir: Path):
    """
    Gera relatório JSON para uma run.
    Salva em runs/<run_id>/metrics/report_<timestamp>.json
    """
    _check_requests()

    ts = datetime.now(timezone.utc).isoformat()
    _print(f"[bold cyan]Gerando relatório para run:[/bold cyan] {run_id}")

    # Coleta snapshot atual
    data = _collect_all()

    # Coleta série temporal dos últimos 30min para calcular estatísticas
    stats = {}
    # Chaves por fatia (slice{i}_*) em vez de ue1_/ue2_ fixos, e RTT como
    # metrica de latencia — ver nota em _build_queries sobre por que
    # probe_duration_seconds foi descartada.
    range_queries = {}
    for i in _slice_indices():
        ip = _UE_IPS.get(i, "")
        range_queries[f"slice{i}_rtt_ms"] = (
            f'probe_icmp_duration_seconds{{job="blackbox-ping-slices", '
            f'instance="{ip}", phase="rtt"}} * 1000'
        )
        range_queries[f"slice{i}_probe_success"] = (
            f'probe_success{{job="blackbox-ping-slices", instance="{ip}"}}'
        )
    range_queries["amf_reg_rate"] = 'rate(fivegs_amffunction_rm_reginitreq{job="amf"}[1m])'

    # Recursos por container. Sao a VARIAVEL DE CONTROLE da analise de
    # isolamento: quando uma fatia degrada durante um experimento, existem duas
    # explicacoes concorrentes — falha de isolamento de rede ou contencao por
    # recursos compartilhados do hospedeiro. Sem estas series nao ha como
    # distinguir uma da outra, e nenhuma conclusao sobre isolamento se sustenta.
    for i in _slice_indices():
        range_queries[f"slice{i}_upf_cpu_pct"] = f'fair5g_container_cpu_percent{{name="upf{i}"}}'
        range_queries[f"slice{i}_ue_cpu_pct"] = f'fair5g_container_cpu_percent{{name="mn.ue{i}"}}'
    for nome in ("gnb", "amf", "onos-controller"):
        chave = nome.replace("-", "_")
        range_queries[f"compartilhado_{chave}_cpu_pct"] = (
            f'fair5g_container_cpu_percent{{name="{nome}"}}'
        )

    now = int(time.time())
    start = now - 1800  # últimos 30 min

    for key, query in range_queries.items():
        try:
            resp = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start,
                    "end": now,
                    "step": "10s",
                },
                timeout=10,
            )
            results = resp.json().get("data", {}).get("result", [])
            if results:
                values = [float(v[1]) for v in results[0]["values"] if v[1] != "NaN"]
                if values:
                    ordenado = sorted(values)
                    n = len(ordenado)
                    # Mediana e percentis, alem da media: distribuicoes de
                    # latencia e jitter tem cauda pesada, e a media e puxada por
                    # valores extremos. A literatura de medicao de redes
                    # recomenda relatar mediana e percentis de cauda.
                    mediana = (ordenado[n // 2] if n % 2
                               else (ordenado[n // 2 - 1] + ordenado[n // 2]) / 2)
                    stats[key] = {
                        "min":    round(min(values), 4),
                        "max":    round(max(values), 4),
                        "mean":   round(sum(values) / len(values), 4),
                        "median": round(mediana, 4),
                        "p95":    round(ordenado[min(int(n * 0.95), n - 1)], 4),
                        "count":  n,
                    }
                else:
                    stats[key] = None
            else:
                stats[key] = None
        except Exception as e:
            stats[key] = {"error": str(e)}

    # Monta o documento JSON
    report = {
        "run_id":       run_id,
        "generated_at": ts,
        "prometheus":   PROMETHEUS_URL,
        "grafana":      GRAFANA_URL,
        "ue_ips":       {f"slice{i}": _UE_IPS.get(i, "") for i in _slice_indices()},
        "snapshot":     {
            cat: {k: v for k, v in metrics.items()}
            for cat, metrics in data.items()
        },
        "statistics_last_30min": stats,
        "comparativo_por_fatia": _slice_comparison(stats),
    }

    # Salva o arquivo
    out_dir = runs_dir / run_id / "metrics"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"report_{ts_file}.json"

    out_file.write_text(json.dumps(report, indent=2, default=str))
    _print(f"[green]Relatório salvo:[/green] {out_file}" if HAS_RICH else f"Relatório salvo: {out_file}")

    # Exibe resumo no terminal
    _print_report_summary(report)
    return out_file


def _slice_comparison(stats: dict) -> dict:
    """Consolida, lado a lado, o que foi medido em cada fatia.

    ESTA FUNCAO NAO EMITE VEREDITO, e isso e deliberado.

    A versao anterior (`_assess_isolation`) imprimia "ISOLAMENTO OK" ou
    "POSSIVEL FALHA DE ISOLAMENTO" a partir de uma unica condicao: a razao
    entre a latencia media do UE1 e a do UE2. Essa heuristica nao sustenta o
    que o nome promete, por tres motivos:

      1. Nao havia carga aplicada nem cenario de controle. Isolamento so pode
         ser avaliado comparando uma fatia perturbada com uma fatia observada,
         sob condicao adversa conhecida e contra uma linha de base.
      2. O resultado era descorrelacionado do fenomeno: em ambiente ocioso a
         razao fica proxima de 1 e a funcao acusava "possivel falha"; um jitter
         aleatorio em uma das fatias produzia "isolamento OK".
      3. Nao considerava recursos do hospedeiro, entao nao distinguia falha de
         isolamento de rede de contencao por CPU compartilhada.

    Um veredito automatico e sedutor porque e facil de citar, mas um rotulo
    errado num relatorio e pior que rotulo nenhum: ele se propaga para figuras
    e conclusoes sem que ninguem revise a premissa. A interpretacao dos dados
    cabe a quem projetou o experimento e conhece as condicoes em que ele rodou.

    O que esta funcao entrega e o material para essa interpretacao: metricas de
    rede por fatia (mediana e p95, nao media), o consumo de recurso do
    componente dedicado de cada fatia, e o consumo dos componentes
    compartilhados — que e a variavel de controle sem a qual nao se distingue
    falha de isolamento de contencao de recursos.
    """
    def _resumo(chave):
        v = stats.get(chave)
        if isinstance(v, dict) and "median" in v:
            return {k: v[k] for k in ("median", "p95", "max", "count") if k in v}
        return None

    por_fatia = {}
    for i in _slice_indices():
        por_fatia[f"fatia_{i}"] = {
            "rtt_ms":        _resumo(f"slice{i}_rtt_ms"),
            "probe_success": _resumo(f"slice{i}_probe_success"),
            "upf_cpu_pct":   _resumo(f"slice{i}_upf_cpu_pct"),
            "ue_cpu_pct":    _resumo(f"slice{i}_ue_cpu_pct"),
        }

    compartilhados = {}
    for nome in ("gnb", "amf", "onos-controller"):
        chave = nome.replace("-", "_")
        compartilhados[nome] = {"cpu_pct": _resumo(f"compartilhado_{chave}_cpu_pct")}

    return {
        "janela": "ultimos 30 min",
        "por_fatia": por_fatia,
        "compartilhados": compartilhados,
        "nota": (
            "Dados brutos para interpretacao. Nenhum veredito de isolamento e "
            "emitido automaticamente: afirmacoes sobre isolamento exigem cenario "
            "controlado (fatia perturbada versus fatia observada), linha de base "
            "para comparacao, repeticoes suficientes para distinguir efeito de "
            "ruido, e verificacao de que os componentes compartilhados nao "
            "estavam saturados durante a medicao."
        ),
    }


def _print_report_summary(report: dict):
    """Exibe resumo legivel do relatorio no terminal.

    Apresenta os dados lado a lado, sem emitir julgamento sobre isolamento —
    ver a justificativa em _slice_comparison.
    """
    comp = report.get("comparativo_por_fatia", {})
    por_fatia = comp.get("por_fatia", {})
    compartilhados = comp.get("compartilhados", {})

    def _c(d, campo, casas=2):
        if isinstance(d, dict) and d.get(campo) is not None:
            return f"{d[campo]:.{casas}f}"
        return "-"

    if HAS_RICH:
        tbl = Table(
            title="Comparativo por fatia (ultimos 30 min)",
            box=box.SIMPLE_HEAVY,
        )
        tbl.add_column("Fatia", style="bold")
        tbl.add_column("RTT mediana (ms)", justify="right")
        tbl.add_column("RTT p95 (ms)", justify="right")
        tbl.add_column("Probe (mediana)", justify="right")
        tbl.add_column("CPU UPF (%)", justify="right")
        tbl.add_column("CPU UE (%)", justify="right")
        tbl.add_column("Amostras", justify="right")

        for nome, v in por_fatia.items():
            rtt = v.get("rtt_ms") or {}
            tbl.add_row(
                nome.replace("_", " ").capitalize(),
                _c(v.get("rtt_ms"), "median"),
                _c(v.get("rtt_ms"), "p95"),
                _c(v.get("probe_success"), "median"),
                _c(v.get("upf_cpu_pct"), "median"),
                _c(v.get("ue_cpu_pct"), "median"),
                str(rtt.get("count", "-")),
            )
        console.print(tbl)

        tbl2 = Table(
            title="Componentes compartilhados — variavel de controle",
            box=box.SIMPLE_HEAVY,
        )
        tbl2.add_column("Componente", style="bold")
        tbl2.add_column("CPU mediana (%)", justify="right")
        tbl2.add_column("CPU p95 (%)", justify="right")
        tbl2.add_column("CPU max (%)", justify="right")
        for nome, v in compartilhados.items():
            tbl2.add_row(
                nome,
                _c(v.get("cpu_pct"), "median"),
                _c(v.get("cpu_pct"), "p95"),
                _c(v.get("cpu_pct"), "max"),
            )
        console.print(tbl2)

        console.print(Panel(
            comp.get("nota", ""),
            title="[bold]Como ler estes numeros[/bold]",
            border_style="cyan",
        ))
    else:
        print("\n=== Comparativo por fatia (ultimos 30 min) ===")
        for nome, v in por_fatia.items():
            rtt = v.get("rtt_ms") or {}
            print(f"  {nome}: RTT mediana={_c(v.get('rtt_ms'), 'median')} ms "
                  f"p95={_c(v.get('rtt_ms'), 'p95')} ms | "
                  f"CPU UPF={_c(v.get('upf_cpu_pct'), 'median')}% | "
                  f"CPU UE={_c(v.get('ue_cpu_pct'), 'median')}% | "
                  f"amostras={rtt.get('count', '-')}")
        print("\n=== Componentes compartilhados (variavel de controle) ===")
        for nome, v in compartilhados.items():
            print(f"  {nome}: CPU mediana={_c(v.get('cpu_pct'), 'median')}% "
                  f"p95={_c(v.get('cpu_pct'), 'p95')}% "
                  f"max={_c(v.get('cpu_pct'), 'max')}%")
        print("\n" + comp.get("nota", ""))


def cmd_open_grafana():
    """Abre o dashboard Grafana no browser padrão."""
    url = f"{GRAFANA_URL}{GRAFANA_DASHBOARD}"
    _print(f"[cyan]Abrindo Grafana:[/cyan] {url}" if HAS_RICH else f"Abrindo Grafana: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        # Fallback para ambientes sem display
        for cmd in [f"xdg-open '{url}'", f"open '{url}'"]:
            if subprocess.call(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                break
        else:
            _print(f"[yellow]Não foi possível abrir o browser. Acesse manualmente:[/yellow] {url}"
                   if HAS_RICH else f"Acesse manualmente: {url}")


# ── menu interativo ───────────────────────────────────────────────────────────

def menu_metrics(runs_dir: Path):
    """
    Submenu de métricas — chamado a partir do main.py.
    Segue o mesmo padrão de _menu_select do projeto.
    """
    try:
        import questionary
        def select(title, choices):
            ans = questionary.select(title, choices=choices).ask()
            if ans is None:
                raise KeyboardInterrupt()
            return ans
        def text(prompt, default=""):
            ans = questionary.text(prompt, default=default).ask()
            if ans is None:
                raise KeyboardInterrupt()
            return ans.strip() or default
    except ImportError:
        def select(title, choices):
            print(title)
            for i, c in enumerate(choices, 1):
                print(f"  {i}) {c}")
            while True:
                raw = input("Escolha um número: ").strip()
                if raw.isdigit() and 1 <= int(raw) <= len(choices):
                    return choices[int(raw) - 1]
        def text(prompt, default=""):
            raw = input(f"{prompt} ").strip()
            return raw or default

    choice = select(
        "Métricas — selecione uma opção:",
        [
            "snapshot (consultar métricas agora)",
            "watch (monitorar em tempo real)",
            "report (gerar relatório de uma run)",
            "grafana (abrir dashboard no browser)",
            "voltar",
        ],
    )

    if choice.startswith("snapshot"):
        cmd_snapshot()

    elif choice.startswith("watch"):
        interval_str = text("Intervalo de refresh em segundos (ENTER para 5s):", default="5")
        try:
            interval = int(interval_str)
        except ValueError:
            interval = 5
        cmd_watch(interval=interval)

    elif choice.startswith("report"):
        # Lista runs disponíveis
        available_runs = sorted(
            [d.name for d in runs_dir.iterdir() if d.is_dir()],
            reverse=True,
        ) if runs_dir.exists() else []

        if available_runs:
            run_choices = available_runs[:10] + ["digitar manualmente"]
            run_choice = select("Selecione a run:", run_choices)
            if run_choice == "digitar manualmente":
                run_id = text("Run ID:")
            else:
                run_id = run_choice
        else:
            run_id = text("Run ID (nenhuma run encontrada, digite manualmente):")

        if run_id:
            cmd_report(run_id, runs_dir)

    elif choice.startswith("grafana"):
        cmd_open_grafana()

    # "voltar" — retorna ao menu principal
