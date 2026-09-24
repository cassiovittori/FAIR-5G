from datetime import datetime, timezone
from sqlmodel import Session, select
from models import User


def create_user(session: Session, email: str, password_hash: str, role: str) -> User:
    user = User(
        email=email,
        password_hash=password_hash,
        role=role,
        created_at=datetime.now(timezone.utc),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email)).first()


def any_admin_exists(session: Session) -> bool:
    return session.exec(select(User).where(User.role == "admin")).first() is not None