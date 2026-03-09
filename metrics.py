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
GRAFANA_DASHBOARD = os.environ.get(
    "GRAFANA_DASHBOARD",
    "/d/open5gs-slice-monitor/open5gs-monitoramento-de-isolamento-de-slices"
)

UE1_IP = os.environ.get("UE1_IP", "10.33.33.200")
UE2_IP = os.environ.get("UE2_IP", "10.33.33.201")

# Queries Prometheus organizadas por categoria
QUERIES = {
    "Conectividade": {
        "Probe UE1 (OK=1)":   f'probe_success{{job="blackbox-ping-slices", instance="{UE1_IP}"}}',
        "Probe UE2 (OK=1)":   f'probe_success{{job="blackbox-ping-slices", instance="{UE2_IP}"}}',
    },
    "Latencia (ms)": {
        "UE1 Latencia Total":  f'probe_duration_seconds{{job="blackbox-ping-slices", instance="{UE1_IP}"}} * 1000',
        "UE2 Latencia Total":  f'probe_duration_seconds{{job="blackbox-ping-slices", instance="{UE2_IP}"}} * 1000',
        "UE1 RTT ICMP":        f'probe_icmp_duration_seconds{{job="blackbox-ping-slices", instance="{UE1_IP}", phase="rtt"}} * 1000',
        "UE2 RTT ICMP":        f'probe_icmp_duration_seconds{{job="blackbox-ping-slices", instance="{UE2_IP}", phase="rtt"}} * 1000',
    },
    "AMF": {
        "UEs Registrados":     'ran_ue{job="amf"}',
        "Sessoes AMF":         'amf_session{job="amf"}',
        "Taxa Registro (r/s)": 'rate(fivegs_amffunction_rm_reginitreq{job="amf"}[1m])',
        "Taxa Auth (r/s)":     'rate(fivegs_amffunction_amf_authreq{job="amf"}[1m])',
    },
    "SMF": {
        "PDU Sessions SMF1":   'fivegs_smffunction_sm_pdusessioncreationreq{job="smf", instance="smf1.open5gs.org:9090"}',
        "PDU Sessions SMF2":   'fivegs_smffunction_sm_pdusessioncreationreq{job="smf", instance="smf2.open5gs.org:9090"}',
    },
    "UPF": {
        "Sessoes UPF1":        'fivegs_upffunction_upf_sessionnbr{job="upf", instance="upf1.open5gs.org:9090"}',
        "Sessoes UPF2":        'fivegs_upffunction_upf_sessionnbr{job="upf", instance="upf2.open5gs.org:9090"}',
        "QoS Flows UPF1":      'fivegs_upffunction_upf_qosflows{job="upf", instance="upf1.open5gs.org:9090"}',
        "QoS Flows UPF2":      'fivegs_upffunction_upf_qosflows{job="upf", instance="upf2.open5gs.org:9090"}',
        "GTP Ingress UPF1 (p/s)": 'rate(fivegs_ep_n3_gtp_indatapktn3upf{job="upf", instance="upf1.open5gs.org:9090"}[1m])',
        "GTP Ingress UPF2 (p/s)": 'rate(fivegs_ep_n3_gtp_indatapktn3upf{job="upf", instance="upf2.open5gs.org:9090"}[1m])',
    },
}

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
    range_queries = {
        "ue1_latency_ms":  f'probe_duration_seconds{{job="blackbox-ping-slices", instance="{UE1_IP}"}} * 1000',
        "ue2_latency_ms":  f'probe_duration_seconds{{job="blackbox-ping-slices", instance="{UE2_IP}"}} * 1000',
        "ue1_probe_success": f'probe_success{{job="blackbox-ping-slices", instance="{UE1_IP}"}}',
        "ue2_probe_success": f'probe_success{{job="blackbox-ping-slices", instance="{UE2_IP}"}}',
        "amf_reg_rate":    'rate(fivegs_amffunction_rm_reginitreq{job="amf"}[1m])',
    }

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
                    stats[key] = {
                        "min":    round(min(values), 4),
                        "max":    round(max(values), 4),
                        "mean":   round(sum(values) / len(values), 4),
                        "p95":    round(sorted(values)[int(len(values) * 0.95)], 4),
                        "count":  len(values),
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
        "ue_ips":       {"ue1": UE1_IP, "ue2": UE2_IP},
        "snapshot":     {
            cat: {k: v for k, v in metrics.items()}
            for cat, metrics in data.items()
        },
        "statistics_last_30min": stats,
        "isolation_assessment": _assess_isolation(stats),
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


def _assess_isolation(stats: dict) -> dict:
    """
    Avalia isolamento de slice comparando métricas das duas UEs.
    Retorna um dict com veredicto e motivo.
    """
    assessment = {"verdict": "INDETERMINADO", "reasons": []}

    ue1 = stats.get("ue1_latency_ms")
    ue2 = stats.get("ue2_latency_ms")

    if not ue1 or not ue2:
        assessment["reasons"].append("Dados insuficientes para avaliação.")
        return assessment

    # Se UE1 tem latência alta mas UE2 está estável — isolamento OK
    latency_ratio = ue1["mean"] / ue2["mean"] if ue2["mean"] > 0 else 1.0
    max_ratio = ue1["max"] / ue2["max"] if ue2["max"] > 0 else 1.0

    if latency_ratio > 3.0:
        assessment["verdict"] = "ISOLAMENTO OK"
        assessment["reasons"].append(
            f"Latência UE1 ({ue1['mean']:.1f}ms) muito superior à UE2 ({ue2['mean']:.1f}ms) "
            f"— UE2 não foi impactada pela carga no Slice 1."
        )
    elif latency_ratio > 1.5:
        assessment["verdict"] = "ISOLAMENTO PARCIAL"
        assessment["reasons"].append(
            f"Latência UE1 ({ue1['mean']:.1f}ms) moderadamente superior à UE2 ({ue2['mean']:.1f}ms)."
        )
    else:
        assessment["verdict"] = "POSSIVEL FALHA DE ISOLAMENTO"
        assessment["reasons"].append(
            f"Latências similares — UE1 mean={ue1['mean']:.1f}ms, UE2 mean={ue2['mean']:.1f}ms. "
            f"Possível recurso compartilhado sendo saturado."
        )

    # Verificar probe_success
    ue1_probe = stats.get("ue1_probe_success")
    ue2_probe = stats.get("ue2_probe_success")
    if ue1_probe and ue1_probe["min"] < 1.0:
        assessment["reasons"].append(f"UE1 teve falhas de probe (min={ue1_probe['min']}).")
    if ue2_probe and ue2_probe["min"] < 1.0:
        assessment["reasons"].append(f"UE2 teve falhas de probe (min={ue2_probe['min']}).")

    return assessment


def _print_report_summary(report: dict):
    """Exibe resumo legível do relatório no terminal."""
    stats = report.get("statistics_last_30min", {})
    assessment = report.get("isolation_assessment", {})

    if HAS_RICH:
        # Tabela de estatísticas
        tbl = Table(title="Resumo Estatístico (últimos 30min)", box=box.SIMPLE_HEAVY)
        tbl.add_column("Métrica",  style="bold")
        tbl.add_column("Min",  justify="right")
        tbl.add_column("Mean", justify="right")
        tbl.add_column("P95",  justify="right")
        tbl.add_column("Max",  justify="right")

        labels = {
            "ue1_latency_ms":   "UE1 Latência (ms)",
            "ue2_latency_ms":   "UE2 Latência (ms)",
            "ue1_probe_success": "UE1 Probe Success",
            "ue2_probe_success": "UE2 Probe Success",
            "amf_reg_rate":     "AMF Reg Rate (r/s)",
        }

        for key, label in labels.items():
            s = stats.get(key)
            if s and isinstance(s, dict) and "mean" in s:
                tbl.add_row(
                    label,
                    str(s["min"]),
                    str(s["mean"]),
                    str(s["p95"]),
                    str(s["max"]),
                )
            else:
                tbl.add_row(label, "-", "-", "-", "-")

        console.print(tbl)

        # Veredicto de isolamento
        verdict = assessment.get("verdict", "INDETERMINADO")
        color = {
            "ISOLAMENTO OK": "green",
            "ISOLAMENTO PARCIAL": "yellow",
            "POSSIVEL FALHA DE ISOLAMENTO": "red",
        }.get(verdict, "white")

        console.print(Panel(
            "\n".join([f"[{color}]{verdict}[/{color}]"] + assessment.get("reasons", [])),
            title="[bold]Avaliação de Isolamento[/bold]",
            border_style=color,
        ))
    else:
        print("\n=== Resumo Estatístico (últimos 30min) ===")
        for key, s in stats.items():
            if s and isinstance(s, dict) and "mean" in s:
                print(f"  {key}: min={s['min']} mean={s['mean']} p95={s['p95']} max={s['max']}")
        print(f"\nVeredicto: {assessment.get('verdict', 'INDETERMINADO')}")
        for r in assessment.get("reasons", []):
            print(f"  - {r}")


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
