#!/usr/bin/env python3
import importlib
import logging
import time
import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

def is_interactive_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()

def show_banner():
    title = "FAIR-5G"
    try:
        import pyfiglet
        banner = pyfiglet.figlet_format(title, font="slant")
    except Exception:
        banner = f"=== {title} ==="

    try:
        from rich.console import Console
        console = Console()
        console.print(f"[bold cyan]{banner}[/bold cyan]")
        console.print("[dim]FAIR5G: Open5GS + Slicing + SDN + Metrics[/dim]\n")
    except Exception:
        print(banner)
        print("FAIR5G: Open5GS + Slicing + SDN + Metrics\n")

def _menu_select(title: str, choices: list[str]) -> str:
    try:
        import questionary
        ans = questionary.select(title, choices=choices).ask()
        if ans is None:
            raise KeyboardInterrupt()
        return ans
    except Exception:
        print(title)
        for i, c in enumerate(choices, 1):
            print(f"  {i}) {c}")
        while True:
            raw = input("Escolha um número: ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(choices):
                return choices[int(raw) - 1]

def _menu_text(prompt: str, default: str = "") -> str:
    try:
        import questionary
        ans = questionary.text(prompt, default=default).ask()
        if ans is None:
            raise KeyboardInterrupt()
        return ans.strip()
    except Exception:
        raw = input(f"{prompt} ").strip()
        return raw or default

def maybe_run_interactive_menu():
    force_menu = "--menu" in sys.argv
    if force_menu:
        sys.argv.remove("--menu")

    no_cmd = len(sys.argv) <= 1
    if not (force_menu or no_cmd):
        return

    if not is_interactive_tty():
        return

    show_banner()

    choice = _menu_select(
        "Selecione uma opção:",
        [
            "up (subir ambiente)",
            "down (derrubar ambiente)",
            "status (ver status)",
            "logs (ver logs de um serviço)",
            "render (renderizar UE runtime)",
            "bootstrap (instalar dependências)",
            "metrics (monitoramento e métricas)",
            "sair",
        ],
    )

    if choice.startswith("up"):
        sys.argv = [sys.argv[0], "up"]
        cfg = _menu_text("Config dir (ENTER para padrão):", default="")
        if cfg:
            sys.argv += ["--config-dir", cfg]
        return

    if choice.startswith("down"):
        sys.argv = [sys.argv[0], "down"]
        wipe = _menu_select("Wipe volumes?", ["não", "sim"])
        if wipe == "sim":
            sys.argv.append("--wipe")
        keep = _menu_select("Manter ONOS container?", ["não", "sim"])
        if keep == "sim":
            sys.argv.append("--keep-onos")
        return

    if choice.startswith("status"):
        sys.argv = [sys.argv[0], "status"]
        return

    if choice.startswith("logs"):
        svc = _menu_text("Serviço (ex: amf, smf1, upf1, gnb):", default="amf")
        sys.argv = [sys.argv[0], "logs", svc]
        return

    if choice.startswith("render"):
        sys.argv = [sys.argv[0], "render"]
        return

    if choice.startswith("bootstrap"):
        sys.argv = [sys.argv[0], "bootstrap"]
        return

    if choice.startswith("metrics"):
        # Importa e delega ao submenu de métricas
        # Não injeta sys.argv — executa direto e encerra
        try:
            from metrics import menu_metrics
        except ImportError:
            # Tenta carregar do diretório do projeto
            sys.path.insert(0, str(REPO_ROOT))
            from metrics import menu_metrics

        runs_dir = REPO_ROOT / "runs"
        menu_metrics(runs_dir)
        raise SystemExit(0)

    raise SystemExit(0)


def run_simple(cmd, cwd=None, env=None):
    print(f"[cmd] {cmd}")
    rc = subprocess.call(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        shell=True,
    )
    if rc != 0:
        raise SystemExit(rc)

def run_capture(cmd, cwd=None, env=None):
    print(f"[cmd] {cmd}")
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        shell=True,
        text=True,
    )
    if p.returncode != 0:
        raise SystemExit(p.returncode)

def run_interactive_logged(cmd, log_path: Path, cwd=None, env=None):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if subprocess.call("command -v script >/dev/null 2>&1", shell=True) != 0:
        print("[ERRO] comando 'script' não encontrado. Instale: sudo apt-get install -y util-linux")
        raise SystemExit(1)

    script_cmd = f"script -q -f {str(log_path)} -c {repr(cmd)}"
    print(f"[cmd] {script_cmd}")
    rc = subprocess.call(
        script_cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        shell=True,
    )
    if rc != 0:
        raise SystemExit(rc)

def new_run_id():
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")

def runs_dir(run_id: str) -> Path:
    return REPO_ROOT / "runs" / run_id

def main():
    maybe_run_interactive_menu()
    parser = argparse.ArgumentParser(prog="fair5gctl", add_help=True)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("bootstrap", help="Instala prereqs no Ubuntu")
    sub.add_parser("render", help="Renderiza configs runtime do UE (gnbSearchList)")

    p_up = sub.add_parser("up", help="Sobe Open5GS + ONOS + Containernet")
    p_up.add_argument("--run-id", default=None)
    p_up.add_argument("--config-dir", default=None)

    p_down = sub.add_parser("down", help="Derruba Open5GS e limpa mininet/containernet")
    p_down.add_argument("--wipe", action="store_true")
    p_down.add_argument("--keep-onos", action="store_true")

    sub.add_parser("status", help="Mostra status")

    p_logs = sub.add_parser("logs", help="Logs do compose")
    p_logs.add_argument("svc")

    # subcomando metrics também disponível via CLI direta
    p_metrics = sub.add_parser("metrics", help="Monitoramento e métricas")
    p_metrics.add_argument(
        "action",
        choices=["snapshot", "watch", "report", "grafana"],
        nargs="?",
        default=None,
    )
    p_metrics.add_argument("--run-id", default=None, help="Run ID para o relatório")
    p_metrics.add_argument("--interval", type=int, default=5, help="Intervalo do watch em segundos")

    args = parser.parse_args()

    if args.cmd == "bootstrap":
        run_simple("./scripts/bootstrap_ubuntu.sh", cwd=REPO_ROOT)
        return

    if args.cmd == "render":
        run_simple("./scripts/render_ue_configs.sh", cwd=REPO_ROOT)
        return

    if args.cmd == "up":
        run_id = args.run_id or new_run_id()
        out = runs_dir(run_id)
        out.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        if args.config_dir:
            env["FAIR5G_CONFIG_DIR"] = args.config_dir
        log_file = out / "up.log"
        run_simple("sudo -v")
        run_interactive_logged("./scripts/up_v0.sh", log_file, cwd=REPO_ROOT, env=env)
        print(f"[ok] run_id={run_id} logs={log_file}")
        return

    if args.cmd == "down":
        env = os.environ.copy()
        if args.wipe:
            env["FAIR5G_WIPE"] = "1"
        if args.keep_onos:
            env["FAIR5G_KEEP_ONOS"] = "1"
        run_simple("./scripts/down_v0.sh", cwd=REPO_ROOT, env=env)
        return

    if args.cmd == "status":
        run_simple("sudo docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'")
        run_simple("(cd compose-files/network-slicing && sudo docker compose ps) || true", cwd=REPO_ROOT)
        run_simple("sudo docker network ls | grep -E 'open5gs' || true")
        return

    if args.cmd == "logs":
        run_simple(f"(cd compose-files/network-slicing && sudo docker compose logs --tail=200 {args.svc})", cwd=REPO_ROOT)
        return

    if args.cmd == "metrics":
        try:
            from metrics import cmd_snapshot, cmd_watch, cmd_report, cmd_open_grafana, menu_metrics
        except ImportError:
            sys.path.insert(0, str(REPO_ROOT))
            from metrics import cmd_snapshot, cmd_watch, cmd_report, cmd_open_grafana, menu_metrics

        _runs_dir = REPO_ROOT / "runs"
        action = args.action

        if action is None:
            # sem subação — abre submenu interativo
            menu_metrics(_runs_dir)
        elif action == "snapshot":
            cmd_snapshot()
        elif action == "watch":
            cmd_watch(interval=args.interval)
        elif action == "report":
            run_id = args.run_id or new_run_id()
            cmd_report(run_id, _runs_dir)
        elif action == "grafana":
            cmd_open_grafana()
        return

if __name__ == "__main__":
    main()
