from datetime import datetime, timezone
from sqlmodel import Session, select
from models import Run


def create_run(session: Session, run_id: str, slice_count: int, log_path: str, user_id: int) -> Run:
    run = Run(
        run_id=run_id,
        status="created",
        created_at=datetime.now(timezone.utc),
        slice_count=slice_count,
        log_path=log_path,
        user_id=user_id,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def update_run(session: Session, run_id: str, **fields) -> Run | None:
    run = session.exec(select(Run).where(Run.run_id == run_id)).first()
    if run is None:
        return None
    for key, value in fields.items():
        setattr(run, key, value)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_run(session: Session, run_id: str, user_id: int) -> Run | None:
    return session.exec(
        select(Run).where(Run.run_id == run_id, Run.user_id == user_id)
    ).first()


def get_active_run(session: Session) -> Run | None:
    return session.exec(select(Run).where(Run.status == "running")).first()


def list_runs(session: Session, user_id: int) -> list[Run]:
    return session.exec(
        select(Run).where(Run.user_id == user_id).order_by(Run.created_at.desc())
    ).all()