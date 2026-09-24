from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = "sqlite:///fair5g.db"

# echo=True imprime o SQL gerado no terminal — útil pra ver o que o SQLModel
# tá fazendo por baixo enquanto você pega o jeito; pode trocar pra False depois.
engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session