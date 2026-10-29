from datetime import datetime, timezone
from sqlmodel import Session, select, func
from models import Preset


def create_preset(session: Session, tipo: str, nome: str | None, descricao: str | None, config: dict, user_id: int) -> Preset:
    now = datetime.now(timezone.utc)
    preset = Preset(
        tipo=tipo,
        nome=nome,
        descricao=descricao,
        config=config,
        user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def get_preset(session: Session, preset_id: int, user_id: int) -> Preset | None:
    return session.exec(
        select(Preset).where(Preset.id == preset_id, Preset.user_id == user_id)
    ).first()


def list_presets(session: Session, user_id: int, tipo: str | None = None) -> list[Preset]:
    query = select(Preset).where(Preset.user_id == user_id)
    if tipo is not None:
        query = query.where(Preset.tipo == tipo)
    return session.exec(query.order_by(Preset.updated_at.desc(), Preset.id.desc())).all()


def count_presets(session: Session, user_id: int, tipo: str) -> int:
    return session.exec(
        select(func.count()).select_from(Preset).where(Preset.user_id == user_id, Preset.tipo == tipo)
    ).one()


def update_preset(session: Session, preset: Preset, **fields) -> Preset:
    for key, value in fields.items():
        setattr(preset, key, value)
    preset.updated_at = datetime.now(timezone.utc)
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def delete_preset(session: Session, preset: Preset) -> None:
    session.delete(preset)
    session.commit()
