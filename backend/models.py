from datetime import datetime
from sqlmodel import SQLModel, Field


class Run(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(unique=True, index=True)
    status: str = "created"          # created | running | stopping | stopped | error
    created_at: datetime
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    slice_count: int
    log_path: str
    user_id: int | None = Field(default=None, foreign_key="user.id")

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    role: str          # pesquisador | estudante | instrutor | admin
    is_active: bool = True
    created_at: datetime