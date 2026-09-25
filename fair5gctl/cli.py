import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

from .core.slicing import (
    DEFAULT_SLICE_COUNT,
    MIN_SLICE_COUNT,
    MAX_SLICE_COUNT,
    validate_slice_count,
    validate_ues_per_slice,
    DEFAULT_UES_PER_SLICE,
    MIN_UES_PER_SLICE,
    MAX_UES_PER_SLICE,
)

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

def _perguntar_ues_por_fatia(slices: int):
    """Pergunta, de forma guiada, quantos UEs cada fatia deve ter.

    O menu existe para quem nao quer decorar a sintaxe da linha de comando, entao
    aqui a pergunta e conduzida em vez de exigir o formato "3,1": primeiro se a
    quantidade e a mesma em todas as fatias e, se nao for, pergunta-se fatia a
    fatia. Retorna a string no formato aceito por --ues-per-slice, ou None para
    manter o padrao.

    Toda funcionalidade precisa estar acessivel pelas DUAS interfaces (argumentos
    e menu); do contrario a ferramenta passa a ter capacidades diferentes conforme
    o modo de uso, e a documentacao vira meia verdade.
    """
    padrao = _menu_select(
        f"Quantos UEs por fatia? (padrão: {DEFAULT_UES_PER_SLICE} por fatia)",
        [
            f"Manter o padrão ({DEFAULT_UES_PER_SLICE} por fatia)",
            "Mesma quantidade em todas as fatias",
            "Definir fatia a fatia",
        ],
    )

    if padrao.startswith("Manter"):
        return None

    if padrao.startswith("Mesma"):
        while True:
            raw = _menu_text(
                f"Quantidade de UEs em cada fatia "
                f"[{MIN_UES_PER_SLICE}-{MAX_UES_PER_SLICE}]:",
                default=str(DEFAULT_UES_PER_SLICE),
            )
            try:
                validate_ues_per_slice(raw, slices)
                return raw
            except ValueError as e:
                print(f"[ERRO] {e}")

    valores = []
    for i in range(1, slices + 1):
        while True:
            raw = _menu_text(
                f"  Fatia {i} — quantidade de UEs "
                f"[{MIN_UES_PER_SLICE}-{MAX_UES_PER_SLICE}]:",
                default=str(DEFAULT_UES_PER_SLICE),
            )
            try:
                n = int(raw)
                if not (MIN_UES_PER_SLICE <= n <= MAX_UES_PER_SLICE):
                    raise ValueError(
                        f"fora do intervalo [{MIN_UES_PER_SLICE}, {MAX_UES_PER_SLICE}]"
                    )
                valores.append(str(n))
                break
            except ValueError as e:
                print(f"[ERRO] {e}")

    resumo = ", ".join(f"fatia {i}: {v} UE(s)" for i, v in enumerate(valores, 1))
    print(f"  → {resumo}")
    return ",".join(valores)


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
            "exec (executar comando dentro de um UE)",
            "metrics (monitoramento e métricas)",
            "tutorial (modo educacional guiado)",
            "sair",
        ],
    )

    if choice.startswith("up"):
        sys.argv = [sys.argv[0], "up"]
        cfg = _menu_text("Config dir (ENTER para padrão):", default="")
        if cfg:
            sys.argv += ["--config-dir", cfg]

        while True:
            raw_slices = _menu_text(
                f"Quantidade de fatias [{MIN_SLICE_COUNT}-{MAX_SLICE_COUNT}] "
                f"(ENTER para {DEFAULT_SLICE_COUNT}):",
                default=str(DEFAULT_SLICE_COUNT),
            )
            try:
                slices = validate_slice_count(raw_slices)
                break
            except ValueError as e:
                print(f"[ERRO] {e}")
        sys.argv += ["--slices", str(slices)]

        ues = _perguntar_ues_por_fatia(slices)
        if ues:
            sys.argv += ["--ues-per-slice", ues]
        return

    if choice.startswith("exec"):
        alvo = _menu_text(
            "Nome do UE (ex.: ue1, ou ue1_2 quando há vários na mesma fatia):",
            default="ue1",
        )
        comando = _menu_text(
            "Comando a executar dentro do UE:",
            default="ping -I uesimtun0 -c 3 10.45.0.1",
        )
        sys.argv = [sys.argv[0], "exec", alvo] + comando.split()
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
        from .metrics import menu_metrics

        runs_dir = REPO_ROOT / "runs"
        menu_metrics(runs_dir)
        raise SystemExit(0)

    if choice.startswith("tutorial"):
        sys.argv = [sys.argv[0], "tutorial"]
        return

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

    # -e is essential: without it `script` exits with ITS OWN status,
    # which is zero even when the wrapped command fails. That is why
    # `up` reported "[ok]" after up_v0.sh had aborted with "Compose
    # plugin not found" (observed twice on 2026-09-17). A bring-up that
    # fails while reporting success is the worst kind of bug for
    # measurement work: it lets a campaign collect data from an
    # environment that was never fully up.
    script_cmd = f"script -q -e -f {str(log_path)} -c {repr(cmd)}"
    print(f"[cmd] {script_cmd}")
    rc = subprocess.call(
        script_cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        shell=True,
    )
    if rc != 0:
        raise SystemExit(rc)

def run_background_logged(cmd, log_path: Path, cwd=None, env=None):
    """Dispara o comando em segundo plano, gravando a saida no log.

    Usado pelo modo --detach. A topologia do Containernet precisa de um processo
    vivo para existir, mas esse processo nao precisa ocupar o terminal do
    usuario: a saida vai para o arquivo de log da execucao e o prompt volta.

    DETALHE IMPORTANTE — por que nao usamos start_new_session:
    o cache de credencial do sudo no Ubuntu e vinculado ao terminal de controle
    (tty_tickets). Um processo em sessao nova nao enxerga o ticket criado pelo
    `sudo -v` e, sem terminal para pedir a senha, todo `sudo` interno falha.
    Observado em 2026-09-10: o up abortou em "Docker Compose plugin nao
    encontrado" porque o `sudo docker compose version` nao conseguiu autenticar.
    Mantendo a mesma sessao e apenas um grupo de processos proprio (setpgrp), o
    ticket continua valido e o processo sobrevive ao termino do CLI.

    Retorna o objeto Popen para que o chamador detecte falha precoce.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if subprocess.call("command -v script >/dev/null 2>&1", shell=True) != 0:
        print("[ERRO] comando 'script' nao encontrado. Instale: sudo apt-get install -y util-linux")
        raise SystemExit(1)

    script_cmd = f"script -q -f {str(log_path)} -c {repr(cmd)}"
    saida = open(log_path.parent / "up.stdout.log", "ab")
    return subprocess.Popen(
        script_cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        shell=True,
        stdout=saida,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setpgrp,
    )


def _aguardar_ambiente(proc, pid_file: Path, log_file: Path, limite: int = 600) -> bool:
    """Espera a topologia ficar pronta, com indicador de progresso.

    Falha rapido: se o processo do `up` morrer antes de a topologia registrar o
    pid, aborta a espera e mostra o fim do log em vez de esperar o limite
    inteiro em silencio. Um `up` que falha sem avisar faria um script de
    campanha disparar medicoes contra um ambiente inexistente.
    """
    giro = "|/-\\"
    for decorrido in range(limite):
        if pid_file.exists():
            sys.stdout.write("\r" + " " * 70 + "\r")
            print(f"[ok] ambiente pronto em ~{decorrido}s "
                  f"(topologia pid {pid_file.read_text().strip()})")
            return True
        if proc.poll() is not None:
            sys.stdout.write("\r" + " " * 70 + "\r")
            print(f"[ERRO] o processo de subida terminou (codigo {proc.returncode}) "
                  f"sem deixar o ambiente pronto.")
            print(f"       Ultimas linhas de {log_file}:\n")
            try:
                linhas = log_file.read_text(errors="replace").splitlines()
                for l in linhas[-15:]:
                    print(f"       {l}")
            except Exception:
                print("       (nao foi possivel ler o log)")
            return False
        sys.stdout.write(f"\r  {giro[decorrido % 4]} subindo ambiente... {decorrido}s")
        sys.stdout.flush()
        time.sleep(1)

    sys.stdout.write("\r" + " " * 70 + "\r")
    print(f"[AVISO] ambiente nao ficou pronto em {limite}s. Verifique {log_file}.")
    return False


def new_run_id():
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")

def runs_dir(run_id: str) -> Path:
    return REPO_ROOT / "runs" / run_id


# ── estado do ambiente ────────────────────────────────────────────────────────
# Arquivo gravado pelo `up` e lido por qualquer comando que precise saber COMO o
# ambiente foi levantado (quantas fatias, qual run_id). Sem ele, o comando
# `metrics` executado em outro terminal nao enxerga FAIR5G_SLICE_COUNT — que so
# existe no processo do `up` — e assume o valor padrao, exibindo menos fatias do
# que realmente estao no ar. Observado em 2026-09-09: ambiente com 4 fatias,
# painel mostrando 2, enquanto o AMF reportava 4 UEs registrados.
#
# Este arquivo tambem serve de base para o desacoplamento do ciclo de vida do
# ambiente da CLI interativa do Containernet.

STATE_FILE = REPO_ROOT / ".fair5g_state.json"


def write_state(run_id: str, slice_count: int, config_dir: str = "",
                ues_per_slice=None) -> None:
    payload = {
        "run_id": run_id,
        "slice_count": int(slice_count),
        "ues_per_slice": ues_per_slice,
        "config_dir": config_dir,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        STATE_FILE.write_text(json.dumps(payload, indent=2))
    except Exception as e:
        print(f"[AVISO] nao foi possivel gravar {STATE_FILE.name}: {e}")


def read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def clear_state() -> None:
    try:
        STATE_FILE.unlink()
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[AVISO] nao foi possivel remover {STATE_FILE.name}: {e}")


def main():
    maybe_run_interactive_menu()
    parser = argparse.ArgumentParser(prog="fair5gctl", add_help=True)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("bootstrap", help="Instala prereqs no Ubuntu")
    sub.add_parser("render", help="Renderiza configs runtime do UE (gnbSearchList)")

    p_up = sub.add_parser("up", help="Sobe Open5GS + ONOS + Containernet")
    p_up.add_argument("--run-id", default=None)
    p_up.add_argument("--config-dir", default=None)
    p_up.add_argument(
        "--slices",
        type=int,
        default=None,
        help=f"Quantidade de fatias a provisionar ({MIN_SLICE_COUNT}-{MAX_SLICE_COUNT}, padrão {DEFAULT_SLICE_COUNT})",
    )

    p_up.add_argument(
        "--ues-per-slice",
        default=None,
        help=("UEs por fatia. Um numero aplica a todas (ex.: 3) ou uma lista por "
              "fatia (ex.: 3,1 = tres UEs na fatia 1 e um na fatia 2). A lista "
              "permite concentrar carga em uma fatia e observar a outra, cenario "
              "necessario para os experimentos de isolamento. Maximo 4 por fatia."),
    )
    p_up.add_argument(
        "--detach",
        action="store_true",
        help=("Mantem o ambiente no ar sem abrir a CLI interativa do Containernet. "
              "Necessario para campanhas experimentais automatizadas, onde nao ha "
              "terminal humano segurando a topologia. Use './fair5g exec' para "
              "rodar comandos nos UEs e './fair5g down' para encerrar."),
    )

    p_exec = sub.add_parser(
        "exec",
        help="Executa um comando dentro de um UE (equivale ao prompt do Containernet)",
    )
    p_exec.add_argument("ue", help="Nome do UE, ex.: ue1")
    p_exec.add_argument("comando", nargs=argparse.REMAINDER,
                        help="Comando a executar dentro do UE")

    p_down = sub.add_parser("down", help="Derruba Open5GS e limpa mininet/containernet")
    p_down.add_argument("--wipe", action="store_true")
    p_down.add_argument("--keep-onos", action="store_true")

    sub.add_parser("status", help="Mostra status")

    p_logs = sub.add_parser("logs", help="Logs do compose")
    p_logs.add_argument("svc")

    p_metrics = sub.add_parser("metrics", help="Monitoramento e métricas")
    p_metrics.add_argument(
        "action",
        choices=["snapshot", "watch", "report", "grafana"],
        nargs="?",
        default=None,
    )
    p_metrics.add_argument("--run-id", default=None, help="Run ID para o relatório")
    p_metrics.add_argument("--interval", type=int, default=5, help="Intervalo do watch em segundos")

    p_tutorial = sub.add_parser(
        "tutorial",
        help="Modo educacional: executa baseline passo a passo com interface web"
    )
    p_tutorial.add_argument(
        "--no-browser",
        action="store_true",
        help="Não abre o browser automaticamente (útil em ambientes headless)"
    )

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
        raw_slices = args.slices if args.slices is not None else env.get("FAIR5G_SLICE_COUNT", DEFAULT_SLICE_COUNT)
        try:
            env["FAIR5G_SLICE_COUNT"] = str(validate_slice_count(raw_slices))
        except ValueError as e:
            print(f"[ERRO] {e}")
            raise SystemExit(1)
        if args.ues_per_slice:
            try:
                validate_ues_per_slice(args.ues_per_slice, int(env["FAIR5G_SLICE_COUNT"]))
            except ValueError as e:
                print(f"[ERRO] {e}")
                raise SystemExit(1)
            env["FAIR5G_UES_PER_SLICE"] = str(args.ues_per_slice)
        log_file = out / "up.log"
        run_simple("sudo -v")
        detach = getattr(args, "detach", False)
        if detach:
            env["FAIR5G_DETACH"] = "1"
        write_state(run_id, env["FAIR5G_SLICE_COUNT"], env.get("FAIR5G_CONFIG_DIR", ""),
                    env.get("FAIR5G_UES_PER_SLICE"))

        if detach:
            pid_file = REPO_ROOT / ".fair5g_topology.pid"
            try:
                pid_file.unlink()
            except FileNotFoundError:
                pass
            proc = run_background_logged("./scripts/up_v0.sh", log_file, cwd=REPO_ROOT, env=env)
            print(f"[detach] subindo em segundo plano — log: {log_file}")
            pronto = _aguardar_ambiente(proc, pid_file, log_file)
            if not pronto:
                clear_state()
                print("\n[detach] ambiente NAO esta no ar. "
                      "Rode './fair5g down' para limpar residuos antes de tentar de novo.")
                raise SystemExit(1)
            print(f"[ok] run_id={run_id} logs={log_file}")
            print("     comandos nos UEs: ./fair5g exec ue1 <comando>")
            print("     encerrar:         ./fair5g down")
            return

        run_interactive_logged("./scripts/up_v0.sh", log_file, cwd=REPO_ROOT, env=env)
        print(f"[ok] run_id={run_id} logs={log_file}")
        return

    if args.cmd == "exec":
        if not args.comando:
            print("[ERRO] informe o comando. Ex.: ./fair5g exec ue1 ping -c 3 10.45.0.1")
            raise SystemExit(2)
        container = args.ue if args.ue.startswith("mn.") else f"mn.{args.ue}"
        cmd = " ".join(args.comando)
        # -t apenas quando ha terminal, para nao quebrar uso em script/pipe.
        flags = "-it" if sys.stdin.isatty() and sys.stdout.isatty() else "-i"
        rc = subprocess.call(f"sudo docker exec {flags} {container} sh -lc {shlex.quote(cmd)}",
                             shell=True)
        raise SystemExit(rc)

    if args.cmd == "down":
        env = os.environ.copy()
        if args.wipe:
            env["FAIR5G_WIPE"] = "1"
        if args.keep_onos:
            env["FAIR5G_KEEP_ONOS"] = "1"
        # Se o ambiente subiu em modo desacoplado, sinaliza o processo da
        # topologia ANTES de derrubar o compose: assim a limpeza do Containernet
        # (switch, links, hosts, veth e iptables) roda pelo mesmo caminho do modo
        # interativo, evitando containers mn.* e interfaces orfas.
        pid_file = REPO_ROOT / ".fair5g_topology.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                print(f"[down] sinalizando topologia desacoplada (pid {pid})...")
                subprocess.call(f"sudo kill -TERM {pid}", shell=True)
                for _ in range(30):
                    if subprocess.call(f"sudo kill -0 {pid} 2>/dev/null", shell=True) != 0:
                        break
                    time.sleep(1)
                else:
                    print("[AVISO] topologia nao encerrou em 30s; seguindo com a limpeza.")
            except Exception as e:
                print(f"[AVISO] falha ao sinalizar a topologia: {e}")
            finally:
                try:
                    pid_file.unlink()
                except Exception:
                    pass
        run_simple("./scripts/down_v0.sh", cwd=REPO_ROOT, env=env)
        clear_state()
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
        from .metrics import cmd_snapshot, cmd_watch, cmd_report, cmd_open_grafana, menu_metrics

        _runs_dir = REPO_ROOT / "runs"
        action = args.action

        if action is None:
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

    if args.cmd == "tutorial":
        from .tutorial import run_tutorial_mode

        open_browser = not args.no_browser
        run_tutorial_mode(open_browser=open_browser)
        return
