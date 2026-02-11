#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

def run_simple(cmd, cwd=None, env=None):
    """Executa comando herdando o TTY (stdout/stderr direto no terminal)."""
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
    """Executa comando e captura saída (não interativo)."""
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
    """
    Executa comando interativo em pseudo-TTY e grava tudo em log usando `script`.
    Isso evita a saída 'bugada' do Mininet/Containernet.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if subprocess.call("command -v script >/dev/null 2>&1", shell=True) != 0:
        print("[ERRO] comando 'script' não encontrado. Instale: sudo apt-get install -y util-linux")
        raise SystemExit(1)

    # `script` cria um TTY real e salva tudo no arquivo.
    # -q: quiet, -f: flush, -c: comando
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
    parser = argparse.ArgumentParser(prog="fair5gctl", add_help=True)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("bootstrap", help="Instala prereqs no Ubuntu")
    sub.add_parser("render", help="Renderiza configs runtime do UE (gnbSearchList)")

    p_up = sub.add_parser("up", help="Sobe Open5GS + ONOS + Containernet")
    p_up.add_argument("--run-id", default=None, help="ID da execução (default: timestamp)")
    p_up.add_argument("--config-dir", default=None, help="Override FAIR5G_CONFIG_DIR")

    p_down = sub.add_parser("down", help="Derruba Open5GS e limpa mininet/containernet")
    p_down.add_argument("--wipe", action="store_true", help="Remove volumes do compose (FAIR5G_WIPE=1)")
    p_down.add_argument("--keep-onos", action="store_true", help="Mantém onos-controller (FAIR5G_KEEP_ONOS=1)")

    sub.add_parser("status", help="Mostra status")
    p_logs = sub.add_parser("logs", help="Logs do compose")
    p_logs.add_argument("svc", help="Serviço do compose (ex: gnb, amf, smf1...)")

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
        # up é interativo (entra no containernet CLI) → precisa de TTY real
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

if __name__ == "__main__":
    main()
