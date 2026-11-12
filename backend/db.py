from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from docchat.config import settings

settings.ensure_dirs()
engine = create_engine(
    f"sqlite:///{settings.sqlite_path}", connect_args={"check_same_thread": False}
)


def init_db() -> None:
    import models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
