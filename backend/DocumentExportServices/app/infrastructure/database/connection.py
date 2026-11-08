from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    def __init__(self, database_url: str, pool_min_size: int = 1, pool_max_size: int = 10, timeout_seconds: int = 30) -> None:
        self._database_url = database_url
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._timeout_seconds = timeout_seconds
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    def open(self) -> None:
        if self._engine is None:
            self._engine = create_engine(
                self._database_url, pool_pre_ping=True,
                pool_size=self._pool_min_size, max_overflow=self._pool_max_size - self._pool_min_size,
                pool_timeout=self._timeout_seconds,
                connect_args={"connect_timeout": self._timeout_seconds,
                              "options": f"-c statement_timeout={self._timeout_seconds * 1000}"},
                hide_parameters=True,
            )
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
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
