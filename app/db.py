from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str) -> None:
        self._url: str = url
        connect_args: dict[str, object] = (
            {"check_same_thread": False} if url.startswith("sqlite") else {}
        )
        self._engine: Engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        self._session_factory: sessionmaker[Session] = sessionmaker(
            bind=self._engine, autoflush=False, autocommit=False
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    def create_all(self) -> None:
        Base.metadata.create_all(self._engine)

    def session(self) -> Session:
        return self._session_factory()

    def get_session(self) -> Iterator[Session]:
        s = self._session_factory()
        try:
            yield s
        finally:
            s.close()


db = Database(settings.effective_database_url)


def get_db() -> Iterator[Session]:
    yield from db.get_session()
