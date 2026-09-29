import subprocess
import os
import asyncio
import shlex
import time
import shutil
import psutil
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
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
from network_metrics import collect_network_metrics, collect_network_history, collect_nfs, HISTORY
from pydantic import BaseModel, Field

app = FastAPI()

REPO_ROOT = "/home/ubuntu/FAIR-5G"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
ALLOWED_SELF_SIGNUP_ROLES = {"pesquisador", "estudante", "instrutor"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    with Session(engine) as session:
        if not any_admin_exists(session):
            admin_email = os.environ.get("FAIR5G_ADMIN_EMAIL", "admin@admin.com")
            admin_password = os.environ.get("FAIR5G_ADMIN_PASSWORD", "admin000")
            create_user(session, email=admin_email, password_hash=hash_password(admin_password), role="admin")
            print(f"[auth] admin criado: {admin_email}")


class UpRequest(BaseModel):
    slices: int = Field(2, ge=1, le=8)
    nome: str | None = Field(None, max_length=60)



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

def _bootstrap_checks() -> dict:
    return {
        "docker": shutil.which("docker") is not None,
        "mn": shutil.which("mn") is not None,
        "openflow": os.path.isdir(os.path.join(REPO_ROOT, "openflow")),
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


@app.get("/logs/bootstrap")
async def stream_bootstrap_logs(current_user: User = Depends(get_current_user)):
    log_path = os.path.join(REPO_ROOT, "logs", "bootstrap.log")
    return StreamingResponse(tail_log(log_path), media_type="text/event-stream")

def build_up_args(config: UpRequest) -> list[str]:
    args = ["--slices", str(config.slices)]
    # campo novo do upstream = uma linha nova aqui
    return args

UP_TIMEOUT = 15 * 60  # segundos

def wait_for_up_completion(run_id: str, log_path: str):
    deadline = time.time() + UP_TIMEOUT
    ok = None
    while time.time() < deadline:
        if os.path.exists(log_path):
            with open(log_path, errors="ignore") as f:
                content = f.read()
            if "Script done on" in content:
                ok = 'COMMAND_EXIT_CODE="0"' in content
                break
        time.sleep(2)

    with Session(engine) as session:
        update_run(session, run_id, status="running" if ok else "error")

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

    run_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_path = os.path.join(REPO_ROOT, "runs", run_id, "up.log")
    nome = (body.nome or "").strip() or None

    create_run(
        session,
        run_id=run_id,
        nome=nome,
        slice_count=body.slices,
        config=body.model_dump(),
        log_path=log_path,
        user_id=current_user.id,
    )

    subprocess.Popen(
        ["sudo", "-n", "FAIR5G_NO_CLI=1", "python3", "fair5gctl.py", "up",
        "--run-id", run_id, *build_up_args(body)],
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


def wait_for_down_completion(run_id: str, log_path: str):
    while not os.path.exists(log_path):
        time.sleep(0.5)

    with open(log_path, "r") as f:
        while True:
            line = f.readline()
            if line:
                if line.startswith("Script done on"):
                    break
            else:
                time.sleep(0.5)

    with Session(engine) as session:
        update_run(session, run_id, status="stopped", stopped_at=datetime.now(timezone.utc))


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
        raise HTTPException(status_code=409, detail="Nenhum ambiente ativo pra derrubar (pode estar sendo criado ou encerrado.)")

    down_log_path = os.path.join(REPO_ROOT, "runs", active.run_id, "down.log")
    os.makedirs(os.path.dirname(down_log_path), exist_ok=True)

    down_cmd = "python3 fair5gctl.py down"
    if wipe:
        down_cmd += " --wipe"
    if keep_onos:
        down_cmd += " --keep-onos"

    script_cmd = f"sudo -n script -q -f {shlex.quote(down_log_path)} -c {shlex.quote(down_cmd)}"
    subprocess.Popen(script_cmd, cwd=REPO_ROOT, shell=True)

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
    psutil.cpu_percent()  # "aquece" o cálculo -- primeira leitura real vem só na próxima chamada


@app.get("/metrics/host")
def host_metrics(current_user: User = Depends(get_current_user)):
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
    }

@app.get("/metrics/network")
def network_metrics(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    run = get_active_run(session)
    if run is None:
        return {"available": False, "reason": "nenhum ambiente ativo"}
    try:
        return {"available": True, **collect_network_metrics(run.slice_count)}
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
        return {"available": True, **collect_network_history(run.slice_count, minutes, since, names)}
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