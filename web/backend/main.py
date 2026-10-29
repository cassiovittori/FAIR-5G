import subprocess
import os
import sys
import threading
import asyncio
import shlex
import time
import shutil
import psutil
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from typing import Literal
from fastapi.responses import StreamingResponse, Response
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, Field, Column
from sqlalchemy import JSON

from models import User
from auth import hash_password, verify_password, create_access_token, decode_access_token
from users_store import create_user, get_user_by_email, any_admin_exists
from db import create_db_and_tables, get_session, engine
from runs_store import create_run, update_run, get_run, get_active_run, list_runs, get_busy_run
from presets_store import create_preset, get_preset, list_presets, count_presets, update_preset, delete_preset
from network_metrics import collect_network_metrics, collect_network_history, collect_nfs, HISTORY, REPO_ROOT
from pydantic import BaseModel, Field

app = FastAPI()

# REPO_ROOT vem do network_metrics (calculado a partir do arquivo, não fixo no código)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
ALLOWED_SELF_SIGNUP_ROLES = {"pesquisador", "estudante", "instrutor"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UpRequest(BaseModel):
    slices: int = Field(2, ge=1, le=8)
    nome: str | None = Field(None, max_length=60)
    # um valor por fatia (ou um só, repetido); limites validados pelo upstream no /up
    ues_per_slice: list[int] | None = None


def _validate_ues_per_slice(raw, slice_count: int) -> list[int]:
    """Delega ao upstream (única fonte dos limites). Levanta ValueError se inválido."""
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    from fair5gctl.core.slicing import validate_ues_per_slice
    return validate_ues_per_slice(raw, slice_count)


def validate_up_config(slices, ues_per_slice) -> dict:
    """Valida e normaliza o que vira flag do up (sem `nome`). Usado pelo /up e pelos presets,
    então template/rascunho só guardam config que o /up aceitaria. Levanta HTTPException 422."""
    if isinstance(slices, bool) or not isinstance(slices, int) or not 1 <= slices <= 8:
        raise HTTPException(status_code=422, detail="slices deve ser um inteiro entre 1 e 8")
    try:
        ues = _validate_ues_per_slice(ues_per_slice, slices)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"slices": slices, "ues_per_slice": ues}



class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str


def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)) -> User:
    email = decode_access_token(token)
    if email is None:
        raise HTTPException(status_code=401, detail="token inválido")
    user = get_user_by_email(session, email)
    if user is None:
        raise HTTPException(status_code=401, detail="usuário não encontrado")
    return user


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    result = subprocess.run(
        ["python3", "fair5gctl.py", "status"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return {"output": result.stdout, "errors": result.stderr}

# mesmo nome/env var que sdn/auto_sdn.py e scripts/bootstrap_ubuntu.sh
UE_IMAGE = os.environ.get("FAIR5G_UE_IMAGE", "fair5g-ue:v3.2.7")


def _ue_image_exists() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(["sudo", "-n", "docker", "image", "inspect", UE_IMAGE],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except subprocess.TimeoutExpired:
        return False
    return r.returncode == 0


def _bootstrap_checks() -> dict:
    return {
        "docker": shutil.which("docker") is not None,
        "mn": shutil.which("mn") is not None,
        "openflow": os.path.isdir(os.path.join(REPO_ROOT, "openflow")),
        "ue_image": _ue_image_exists(),
    }


def _bootstrap_already_done() -> bool:
    return all(_bootstrap_checks().values())


@app.get("/bootstrap/status")
def bootstrap_status():
    checks = _bootstrap_checks()
    return {"bootstrapped": all(checks.values()), "checks": checks}


@app.post("/bootstrap")
def bootstrap(
    force: bool = False,
    current_user: User = Depends(get_current_user),
):
    if not force and _bootstrap_already_done():
        return {
            "status": "already_bootstrapped",
            "message": "docker, mn e containernet/openflow já presentes — nada foi executado. Use ?force=true pra rodar mesmo assim.",
        }

    log_path = os.path.join(REPO_ROOT, "logs", "bootstrap.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    # remove log antigo (pode ter ficado dono root de uma tentativa anterior)
    subprocess.run(["sudo", "-n", "rm", "-f", log_path])

    bootstrap_cmd = "./scripts/bootstrap_ubuntu.sh"
    if force:
        bootstrap_cmd += " --force"

    script_cmd = f"script -q -f {shlex.quote(log_path)} -c {shlex.quote(bootstrap_cmd)}"
    subprocess.Popen(script_cmd, cwd=REPO_ROOT, shell=True)

    return {"status": "started"}


# "disjuntor": down sem depender do que o banco acha que está no ar (restos de uma
# subida que falhou, containers de um up pela CLI...). Log próprio, fora de runs/.
CLEANUP_LOG = os.path.join(REPO_ROOT, "logs", "cleanup.log")


def _cleanup_in_progress() -> bool:
    if not os.path.exists(CLEANUP_LOG) or _read_finish(CLEANUP_LOG) is not None:
        return False
    # log sem "Script done" há mais que o timeout do down = processo morreu (reboot etc.)
    return time.time() - os.path.getmtime(CLEANUP_LOG) < DOWN_TIMEOUT


@app.post("/cleanup")
def force_cleanup(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    busy = get_busy_run(session)
    if busy is not None and busy.status in ("starting", "stopping"):
        estados = {"starting": "sendo criado", "stopping": "sendo encerrado"}
        raise HTTPException(status_code=409, detail=f"Há um ambiente {estados[busy.status]}. Aguarde terminar.")
    if _cleanup_in_progress():
        raise HTTPException(status_code=409, detail="Já existe uma limpeza em andamento.")

    if busy is not None:  # running: derruba pelo caminho normal, o run termina como "stopped"
        down_log = _start_down(busy.run_id)
        update_run(session, busy.run_id, status="stopping")
        _spawn(wait_for_down_completion, busy.run_id, down_log)
        return {"log": f"/logs/{busy.run_id}/down"}

    # log antigo pode ser do root (o script roda com sudo)
    subprocess.run(["sudo", "-n", "rm", "-f", CLEANUP_LOG])
    _run_down_script(CLEANUP_LOG)
    return {"log": "/logs/cleanup"}


@app.get("/logs/cleanup")  # antes de /logs/{run_id}, senão "cleanup" vira run_id
async def stream_cleanup_logs(current_user: User = Depends(get_current_user)):
    return StreamingResponse(tail_log(CLEANUP_LOG), media_type="text/event-stream")


@app.get("/logs/bootstrap")
async def stream_bootstrap_logs(current_user: User = Depends(get_current_user)):
    log_path = os.path.join(REPO_ROOT, "logs", "bootstrap.log")
    return StreamingResponse(tail_log(log_path), media_type="text/event-stream")

def build_up_args(config: dict) -> list[str]:
    args = ["--slices", str(config["slices"])]
    # campo novo do upstream = uma linha nova aqui
    if config.get("ues_per_slice"):  # runs antigos não têm: o upstream usa o padrão
        args += ["--ues-per-slice", ",".join(map(str, config["ues_per_slice"]))]
    return args

UP_TIMEOUT = 15 * 60  # segundos
DOWN_TIMEOUT = 10 * 60  # segundos

def _read_finish(log_path: str):
    """None = ainda não terminou; True/False = terminou com/sem exit code 0."""
    if not os.path.exists(log_path):
        return None
    with open(log_path, errors="ignore") as f:
        content = f.read()
    if "Script done on" not in content:
        return None
    return 'COMMAND_EXIT_CODE="0"' in content

# o up_v0.sh recusa subir por cima de um ambiente no ar e sai sem tocar em nada
UP_REFUSED_MARKER = "Nothing was changed."


def _up_was_refused(log_path: str) -> bool:
    if not os.path.exists(log_path):
        return False
    with open(log_path, errors="ignore") as f:
        return UP_REFUSED_MARKER in f.read()


def _start_down(run_id: str, wipe: bool = False, keep_onos: bool = False) -> str:
    """Dispara o fair5gctl down em background, logando em runs/<id>/down.log."""
    down_log_path = os.path.join(REPO_ROOT, "runs", run_id, "down.log")
    return _run_down_script(down_log_path, wipe, keep_onos)


def _run_down_script(down_log_path: str, wipe: bool = False, keep_onos: bool = False) -> str:
    os.makedirs(os.path.dirname(down_log_path), exist_ok=True)

    down_cmd = "python3 fair5gctl.py down"
    if wipe:
        down_cmd += " --wipe"
    if keep_onos:
        down_cmd += " --keep-onos"

    script_cmd = f"sudo -n script -q -f {shlex.quote(down_log_path)} -c {shlex.quote(down_cmd)}"
    subprocess.Popen(script_cmd, cwd=REPO_ROOT, shell=True)
    return down_log_path


def _fail_up(session, run_id: str, log_path: str):
    """Subida falhou (ou estourou o tempo): o que já subiu (core, ONOS...) fica no ar e
    bloqueia o próximo up, então derruba sozinho. O run passa por "stopping" (log do down
    visível no monitoramento) e termina em "error" -- ver wait_for_down_completion.
    Exceção: se o upstream RECUSOU subir, o ambiente no ar não é deste run (pode ser um
    up feito pela CLI) e derrubá-lo seria destrutivo."""
    if _up_was_refused(log_path):
        update_run(session, run_id, status="error")
        print(f"[up] {run_id}: recusado pelo upstream (ambiente já no ar); nada a limpar", flush=True)
        return
    update_run(session, run_id, status="stopping")
    down_log = _start_down(run_id)
    print(f"[up] {run_id}: subida falhou, derrubando o que ficou no ar", flush=True)
    _spawn(wait_for_down_completion, run_id, down_log)


def wait_for_up_completion(run_id: str, log_path: str, timeout: float = UP_TIMEOUT):
    deadline = time.time() + timeout
    ok = None
    while time.time() < deadline:
        finished = _read_finish(log_path)
        if finished is not None:
            ok = finished
            break
        time.sleep(2)

    with Session(engine) as session:
        if ok:
            update_run(session, run_id, status="running")
        else:
            _fail_up(session, run_id, log_path)

@app.post("/up")
def start_testbed(
    body: UpRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    busy = get_busy_run(session)
    if busy is not None:
        estados = {"starting": "sendo criado", "running": "ativo", "stopping": "sendo encerrado"}
        raise HTTPException(status_code=409, detail=f"já existe um ambiente {estados[busy.status]}")
    if _cleanup_in_progress():
        # 423 e não 409: o front trata 409 como "ambiente em uso" e oferece "Parar"
        raise HTTPException(status_code=423, detail="Há uma limpeza em andamento. Aguarde terminar.")

    # nome já tem coluna própria; o config guarda só o que vira flag do up
    config = validate_up_config(body.slices, body.ues_per_slice)

    run_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_path = os.path.join(REPO_ROOT, "runs", run_id, "up.log")
    nome = (body.nome or "").strip() or None

    create_run(
        session,
        run_id=run_id,
        nome=nome,
        slice_count=body.slices,
        config=config,
        log_path=log_path,
        user_id=current_user.id,
    )

    subprocess.Popen(
        ["sudo", "-n", "FAIR5G_NO_CLI=1", "python3", "fair5gctl.py", "up",
        "--run-id", run_id, *build_up_args(config)],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    update_run(session, run_id, status="starting", started_at=datetime.now(timezone.utc))
    background_tasks.add_task(wait_for_up_completion, run_id, log_path)
    return {"run_id": run_id}


@app.get("/runs")
def runs_list(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return list_runs(session, user_id=current_user.id)


@app.get("/runs/{run_id}")
def run_detail(
    run_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    run = get_run(session, run_id, user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="run não encontrado")
    return run


# Presets: templates e rascunhos do formulário de criação ---------------------------------
PRESETS_LIMIT = 50  # por usuário e por tipo


class PresetCreate(BaseModel):
    tipo: Literal["template", "rascunho"]
    nome: str | None = Field(None, max_length=60)
    descricao: str | None = Field(None, max_length=200)
    config: dict


class PresetUpdate(BaseModel):
    nome: str | None = Field(None, max_length=60)
    descricao: str | None = Field(None, max_length=200)
    config: dict | None = None


def _preset_fields(tipo: str, nome: str | None, descricao: str | None) -> dict:
    """Normaliza nome/descrição: template exige nome; rascunho não tem descrição."""
    nome = (nome or "").strip() or None
    if tipo == "template" and nome is None:
        raise HTTPException(status_code=422, detail="template precisa de um nome")
    descricao = ((descricao or "").strip() or None) if tipo == "template" else None
    return {"nome": nome, "descricao": descricao}


def _preset_or_404(session: Session, preset_id: int, user_id: int):
    preset = get_preset(session, preset_id, user_id=user_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="preset não encontrado")
    return preset


@app.get("/presets")
def presets_list(
    tipo: Literal["template", "rascunho"] | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return list_presets(session, user_id=current_user.id, tipo=tipo)


@app.post("/presets", status_code=201)
def preset_create(
    body: PresetCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    fields = _preset_fields(body.tipo, body.nome, body.descricao)
    config = validate_up_config(body.config.get("slices"), body.config.get("ues_per_slice"))
    if count_presets(session, user_id=current_user.id, tipo=body.tipo) >= PRESETS_LIMIT:
        raise HTTPException(status_code=422, detail=f"limite de {PRESETS_LIMIT} itens deste tipo atingido; exclua algum antes")
    return create_preset(session, tipo=body.tipo, config=config, user_id=current_user.id, **fields)


@app.get("/presets/{preset_id}")
def preset_detail(
    preset_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return _preset_or_404(session, preset_id, current_user.id)


@app.put("/presets/{preset_id}")
def preset_update(
    preset_id: int,
    body: PresetUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    preset = _preset_or_404(session, preset_id, current_user.id)
    sent = body.model_dump(exclude_unset=True)  # parcial: só o que veio no body
    fields = _preset_fields(
        preset.tipo,
        sent["nome"] if "nome" in sent else preset.nome,
        sent["descricao"] if "descricao" in sent else preset.descricao,
    )
    if sent.get("config") is not None:
        fields["config"] = validate_up_config(body.config.get("slices"), body.config.get("ues_per_slice"))
    return update_preset(session, preset, **fields)


@app.delete("/presets/{preset_id}", status_code=204)
def preset_delete(
    preset_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    delete_preset(session, _preset_or_404(session, preset_id, current_user.id))
    return Response(status_code=204)


async def tail_log(log_path: str):
    while not os.path.exists(log_path):
        await asyncio.sleep(0.5)

    with open(log_path, "r") as f:
        while True:
            line = f.readline()
            if line:
                yield f"data: {line.rstrip()}\n\n"
                if line.startswith("Script done on"):
                    break
            else:
                await asyncio.sleep(0.5)


@app.get("/logs/{run_id}")
async def stream_up_logs(
    run_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if get_run(session, run_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="run não encontrado")
    log_path = os.path.join(REPO_ROOT, "runs", run_id, "up.log")
    return StreamingResponse(tail_log(log_path), media_type="text/event-stream")



@app.get("/logs/{run_id}/down")
async def stream_down_logs(
    run_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if get_run(session, run_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="run não encontrado")
    log_path = os.path.join(REPO_ROOT, "runs", run_id, "down.log")
    return StreamingResponse(tail_log(log_path), media_type="text/event-stream")


def wait_for_down_completion(run_id: str, log_path: str, timeout: float = DOWN_TIMEOUT):
    deadline = time.time() + timeout
    finished = None
    while time.time() < deadline:
        finished = _read_finish(log_path)
        if finished is not None:
            break
        time.sleep(1)

    with Session(engine) as session:
        if finished is None:
            # down não terminou no prazo: libera o lock e sinaliza o problema
            update_run(session, run_id, status="error")
        else:
            update_run(session, run_id, status=_status_after_down(log_path), stopped_at=datetime.now(timezone.utc))


def _status_after_down(down_log: str) -> str:
    """Down de um ambiente que subiu -> "stopped"; limpeza depois de subida que falhou -> "error".
    Sai do up.log ao lado, então vale também para a reconciliação no startup."""
    up_log = os.path.join(os.path.dirname(down_log), "up.log")
    return "error" if _read_finish(up_log) is False else "stopped"

def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite devolve naive


def _spawn(target, *args):
    threading.Thread(target=target, args=args, daemon=True).start()


def reconcile_stuck_runs(session):
    """Roda no startup: runs presos em starting/stopping (ex.: reload no meio da subida)."""
    stuck = [r for r in list_runs(session) if r.status in ("starting", "stopping")]
    for run in stuck:
        # copia os campos antes: o update_run faz commit e expira o objeto
        run_id, status, log_path = run.run_id, run.status, run.log_path
        started = _aware(run.started_at) or _aware(run.created_at)

        if status == "starting":
            finished = _read_finish(log_path)
            if finished is not None:
                if finished:
                    update_run(session, run_id, status="running")
                else:
                    _fail_up(session, run_id, log_path)
                print(f"[reconcile] {run_id}: starting -> {'running' if finished else 'falhou'} (pelo log)", flush=True)
                continue
            age = (datetime.now(timezone.utc) - started).total_seconds() if started else UP_TIMEOUT
            remaining = UP_TIMEOUT - age
            if remaining <= 0:
                _fail_up(session, run_id, log_path)
                print(f"[reconcile] {run_id}: starting -> falhou (passou de {UP_TIMEOUT // 60} min)", flush=True)
            else:
                _spawn(wait_for_up_completion, run_id, log_path, remaining)
                print(f"[reconcile] {run_id}: starting, esperando o log terminar ({int(remaining)}s restantes)", flush=True)

        else:  # stopping
            down_log = os.path.join(os.path.dirname(log_path), "down.log")
            if _read_finish(down_log) is not None:
                # hora real do fim = última escrita do log
                stopped_at = datetime.fromtimestamp(os.path.getmtime(down_log), timezone.utc)
                new = _status_after_down(down_log)
                update_run(session, run_id, status=new, stopped_at=stopped_at)
                print(f"[reconcile] {run_id}: stopping -> {new} (pelo log)", flush=True)
            else:
                _spawn(wait_for_down_completion, run_id, down_log)
                print(f"[reconcile] {run_id}: stopping, esperando o down.log terminar", flush=True)


@app.post("/down")
def stop_testbed(
    background_tasks: BackgroundTasks,
    wipe: bool = False,
    keep_onos: bool = False,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    active = get_active_run(session)
    if active is None:
        busy = get_busy_run(session)
        if busy is not None and busy.status == "starting":
            detail = "O ambiente ainda está sendo criado. Aguarde ele ficar ativo para poder pará-lo."
        elif busy is not None and busy.status == "stopping":
            detail = "O ambiente já está sendo encerrado."
        else:
            detail = "Nenhum ambiente ativo para parar."
        raise HTTPException(status_code=409, detail=detail)

    down_log_path = _start_down(active.run_id, wipe=wipe, keep_onos=keep_onos)

    update_run(session, active.run_id, status="stopping")
    background_tasks.add_task(wait_for_down_completion, active.run_id, down_log_path)

    return {"run_id": active.run_id, "status": "stopping"}


@app.post("/auth/register", response_model=UserOut)
def register(body: RegisterRequest, session: Session = Depends(get_session)):
    if body.role not in ALLOWED_SELF_SIGNUP_ROLES:
        raise HTTPException(status_code=422, detail=f"role deve ser um de: {', '.join(ALLOWED_SELF_SIGNUP_ROLES)}")

    if get_user_by_email(session, body.email) is not None:
        raise HTTPException(status_code=409, detail="e-mail já cadastrado")

    user = create_user(session, email=body.email, password_hash=hash_password(body.password), role=body.role)
    return user


@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = get_user_by_email(session, form_data.username)
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="e-mail ou senha inválidos")

    token = create_access_token(subject=user.email)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    with Session(engine) as session:
        if not any_admin_exists(session):
            admin_email = os.environ.get("FAIR5G_ADMIN_EMAIL", "admin@admin.com")
            admin_password = os.environ.get("FAIR5G_ADMIN_PASSWORD", "admin000")
            create_user(session, email=admin_email, password_hash=hash_password(admin_password), role="admin")
            print(f"[auth] admin criado: {admin_email}")
        reconcile_stuck_runs(session)  # sempre, não só quando o admin é criado
    psutil.cpu_percent()  # "aquece" o cálculo -- primeira leitura real vem só na próxima chamada


@app.get("/metrics/host")
def host_metrics(current_user: User = Depends(get_current_user)):
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
    }

def _run_ues(run) -> list[int] | None:
    """runs antigos não têm o campo -> None (1 UE por fatia)."""
    return (run.config or {}).get("ues_per_slice")


@app.get("/metrics/network")
def network_metrics(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    run = get_active_run(session)
    if run is None:
        return {"available": False, "reason": "nenhum ambiente ativo"}
    try:
        return {"available": True, **collect_network_metrics(run.slice_count, _run_ues(run))}
    except OSError:  # Prometheus fora do ar ou lento (inclui URLError e timeout)
        return {"available": False, "reason": "prometheus indisponível"}
    
@app.get("/metrics/network/history")
def network_history(
    minutes: int = Query(15, ge=1, le=120),
    metrics: str | None = Query(None),  # ex: packet_loss,jitter_ms
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    names = [n.strip() for n in metrics.split(",") if n.strip()] if metrics else None
    if names:
        invalid = [n for n in names if n not in HISTORY]
        if invalid:
            raise HTTPException(status_code=422, detail=f"métricas desconhecidas: {invalid}")

    run = get_active_run(session)
    if run is None:
        return {"available": False, "reason": "nenhum ambiente ativo"}

    started = run.started_at
    since = None
    if started:
        if started.tzinfo is None:  # o SQLite pode devolver sem timezone
            started = started.replace(tzinfo=timezone.utc)
        since = started.timestamp()

    try:
        return {"available": True, **collect_network_history(run.slice_count, _run_ues(run), minutes, since, names)}
    except OSError:
        return {"available": False, "reason": "prometheus indisponível"}

@app.get("/metrics/network/nfs")
def network_nfs(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if get_active_run(session) is None:
        return {"available": False, "reason": "nenhum ambiente ativo"}
    try:
        return {"available": True, "nfs": collect_nfs()}
    except OSError:
        return {"available": False, "reason": "prometheus indisponível"}