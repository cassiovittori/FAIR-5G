import os

from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = "sqlite:///fair5g.db"

# FAIR5G_SQL_ECHO=1 imprime o SQL gerado no terminal (útil pra debug).
engine = create_engine(DATABASE_URL, echo=os.environ.get("FAIR5G_SQL_ECHO") == "1")


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session