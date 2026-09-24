import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "web" / "backend"
FRONTEND_DIR = REPO_ROOT / "web" / "frontend"
LOGS_DIR = REPO_ROOT / "logs"
BACKEND_ENV_FILE = BACKEND_DIR / ".env"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173

_USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
BLUE, MAGENTA, YELLOW, RED, GREEN = "34", "35", "33", "31", "32"


def _c(text: str, color: str, bold: bool = False) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{'1;' if bold else ''}{color}m{text}\033[0m"


def _highlight_ports(line: str) -> str:
    pattern = rf":({BACKEND_PORT}|{FRONTEND_PORT})\b"
    return re.sub(pattern, lambda m: ":" + _c(m.group(1), YELLOW, bold=True), line)


def _ensure_backend_deps() -> Path:
    venv_python = BACKEND_DIR / "venv" / "bin" / "python"
    if not venv_python.exists():
        print(f"{_c('[web]', GREEN, bold=True)} criando venv do backend...")
        subprocess.check_call([sys.executable, "-m", "venv", "venv"], cwd=BACKEND_DIR)
        subprocess.check_call(
            [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=BACKEND_DIR,
        )
    return venv_python


def _ensure_frontend_deps() -> None:
    if shutil.which("npm") is None:
        print(f"{_c('[ERRO]', RED, bold=True)} 'npm' não encontrado no PATH. Instale Node.js (ex: via nvm).")
        raise SystemExit(1)
    if not (FRONTEND_DIR / "node_modules").exists():
        print(f"{_c('[web]', GREEN, bold=True)} instalando dependências do frontend (npm install)...")
        subprocess.check_call(["npm", "install"], cwd=FRONTEND_DIR)


def _backend_env() -> dict[str, str]:
    env = os.environ.copy()
    if BACKEND_ENV_FILE.exists():
        for line in BACKEND_ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    if not env.get("FAIR5G_JWT_SECRET"):
        secret = secrets.token_urlsafe(48)
        with open(BACKEND_ENV_FILE, "a", encoding="utf-8") as f:
            f.write(f"FAIR5G_JWT_SECRET={secret}\n")
        os.chmod(BACKEND_ENV_FILE, 0o600)
        print(f"{_c('[web]', GREEN, bold=True)} FAIR5G_JWT_SECRET gerado em {BACKEND_ENV_FILE}")
        env["FAIR5G_JWT_SECRET"] = secret
    return env


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _pump(proc: subprocess.Popen, prefix: str, log_path: Path) -> None:
    with open(log_path, "a", encoding="utf-8") as log:
        for line in proc.stdout:
            log.write(line)
            log.flush()
            sys.stdout.write(f"{prefix} {_highlight_ports(line)}")
            sys.stdout.flush()


def _start(cmd: list[str], cwd: Path, prefix: str, log_path: Path, env=None) -> subprocess.Popen:
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    threading.Thread(target=_pump, args=(proc, prefix, log_path), daemon=True).start()
    return proc


def _stop(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        if p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.time() + 5
    for p in procs:
        try:
            p.wait(timeout=max(0.1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)


def run_web_interface(host: str = "127.0.0.1") -> None:
    venv_python = _ensure_backend_deps()
    _ensure_frontend_deps()

    busy = [p for p in (BACKEND_PORT, FRONTEND_PORT) if _port_in_use(p)]
    if busy:
        ports = ", ".join(_c(str(p), YELLOW, bold=True) for p in busy)
        print(f"{_c('[ERRO]', RED, bold=True)} porta(s) em uso: {ports}. A interface já está rodando?")
        raise SystemExit(1)

    # O backend executa 'sudo -n' para up/down; autentica o sudo antes.
    has_sudo = subprocess.call(["sudo", "-n", "true"], stderr=subprocess.DEVNULL) == 0
    if not has_sudo and subprocess.call(["sudo", "-v"]) != 0:
        print(f"{_c('[ERRO]', RED, bold=True)} falha ao autenticar sudo.")
        raise SystemExit(1)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    backend = _start(
        [str(venv_python), "-m", "uvicorn", "main:app", "--reload",
         "--host", host, "--port", str(BACKEND_PORT)],
        BACKEND_DIR, _c("[back ]", BLUE, bold=True), LOGS_DIR / "web-backend.log", env=_backend_env(),
    )
    frontend = _start(
        ["npm", "run", "dev", "--", "--host", host, "--port", str(FRONTEND_PORT), "--strictPort"],
        FRONTEND_DIR, _c("[front]", MAGENTA, bold=True), LOGS_DIR / "web-frontend.log",
    )
    procs = [backend, frontend]

    # Fechar o terminal / cair o SSH (SIGHUP) ou 'kill' (SIGTERM) também derruba back e front.
    def _interrupt(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGHUP, _interrupt)
    signal.signal(signal.SIGTERM, _interrupt)

    web = _c("[web]", GREEN, bold=True)
    print(f"{web} {_c('backend ', BLUE, bold=True)} → http://localhost:{_c(str(BACKEND_PORT), YELLOW, bold=True)}")
    print(f"{web} {_c('frontend', MAGENTA, bold=True)} → http://localhost:{_c(str(FRONTEND_PORT), YELLOW, bold=True)}")
    print(f"{web} Ctrl+C para encerrar.")

    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        dead = "backend" if backend.poll() is not None else "frontend"
        print(f"{_c('[ERRO]', RED, bold=True)} {dead} encerrou inesperadamente; derrubando o outro processo.")
    except KeyboardInterrupt:
        print(f"\n{_c('[web]', GREEN, bold=True)} encerrando...")
    finally:
        _stop(procs)
