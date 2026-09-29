from datetime import datetime
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON


class Run(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(unique=True, index=True)
    nome: str | None = Field(default=None, max_length=60)
    status: str = "created"          # created | running | stopping | stopped | error
    created_at: datetime
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    slice_count: int
    log_path: str
    user_id: int | None = Field(default=None, foreign_key="user.id")
    config: dict | None = Field(default=None, sa_column=Column(JSON))

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    role: str          # pesquisador | estudante | instrutor | admin
    is_active: bool = True
    created_at: datetime