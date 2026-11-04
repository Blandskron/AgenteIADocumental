from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def open(self) -> None:
        if self._engine is None:
            self._engine = create_engine(self._database_url, pool_pre_ping=True)
            self._session_factory = sessionmaker(bind=self._engine, autoflush=False, expire_on_commit=False)

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @contextmanager
    def session(self) -> Iterator[Session]:
        if self._session_factory is None:
            self.open()
        assert self._session_factory is not None
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

