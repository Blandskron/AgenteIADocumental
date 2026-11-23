"""SQL contract and PostgreSQL integration tests for StudioRepositoryPg (EVO-003)."""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.infrastructure.studio_repository_pg import StudioRepositoryPg


class _ScalarResult:
    def __init__(self, scalars: list[Any]) -> None:
        self._scalars = scalars

    def all(self) -> list[Any]:
        return self._scalars


class _RecordingResult:
    def __init__(self, *, rows: list[dict[str, Any]] | None = None, scalars: list[Any] | None = None) -> None:
        self._rows = rows or []
        self._scalars = scalars or []

    def mappings(self) -> _RecordingResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows

    def first(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._scalars)


class _RecordingSession:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, Any]]] = []
        self.commits = 0

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _RecordingResult:
        sql = str(statement)
        self.queries.append((sql, dict(params or {})))
        if "FROM studio.artifact_sources" in sql:
            return _RecordingResult(scalars=["doc-1"])
        if "RETURNING artifact_id" in sql:
            return _RecordingResult(
                rows=[
                    {
                        "artifact_id": (params or {}).get("artifact_id", "art-1"),
                        "collection_id": "col-1",
                        "template_id": "summary.executive",
                        "current_version": 2,
                        "created_at": "2026-11-23T00:00:00+00:00",
                    }
                ]
            )
        if "FROM studio.artifacts a" in sql:
            return _RecordingResult(
                rows=[
                    {
                        "artifact_id": "art-1",
                        "collection_id": "col-1",
                        "template_id": "summary.executive",
                        "title": "Resumen",
                        "status": "FRESH",
                        "version": 1,
                        "current_version": 1,
                        "groundedness_score": 1.0,
                        "content": {"body_md": "hola"},
                        "body_md": "hola",
                        "created_at": "2026-11-23T00:00:00+00:00",
                        "updated_at": "2026-11-23T00:00:00+00:00",
                    }
                ]
            )
        return _RecordingResult()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None


def test_save_artifact_uses_artifact_versions_and_valid_columns() -> None:
    session = _RecordingSession()
    repo = StudioRepositoryPg(session)  # type: ignore[arg-type]

    saved = repo.save_artifact(
        tenant_id="tenant-1",
        owner_user_id="user-1",
        collection_id="col-1",
        template_id="summary.executive",
        title="Resumen Q4",
        content={"template_id": "summary.executive", "title": "Resumen Q4", "body_md": "Contenido"},
        document_ids=["doc-1", "doc-1"],
        groundedness_score=0.98,
    )

    assert saved["version"] == 1
    assert saved["current_version"] == 1
    assert saved["body_md"] == "Contenido"
    assert saved["document_ids"] == ["doc-1"]
    assert session.commits == 1

    sql_statements = [sql for sql, _ in session.queries]
    assert any("INSERT INTO studio.artifacts" in s and "current_version" in s for s in sql_statements)
    assert any("INSERT INTO studio.artifact_versions" in s and "content_json" in s for s in sql_statements)
    assert any("INSERT INTO studio.artifact_sources" in s for s in sql_statements)
    assert all("groundedness_score" not in s or "artifact_versions" in s for s in sql_statements)


def test_list_and_get_artifact_join_artifact_versions() -> None:
    session = _RecordingSession()
    repo = StudioRepositoryPg(session)  # type: ignore[arg-type]

    listed = repo.list_artifacts(tenant_id="tenant-1", owner_user_id="user-1")
    assert len(listed) == 1
    assert listed[0]["version"] == 1

    fetched = repo.get_artifact(artifact_id="art-1", tenant_id="tenant-1", owner_user_id="user-1")
    assert fetched is not None
    assert fetched["document_ids"] == ["doc-1"]

    sql_statements = [sql for sql, _ in session.queries]
    assert any("JOIN studio.artifact_versions" in s for s in sql_statements)


def test_real_postgres_artifact_versioning_and_stale_trigger() -> None:
    db_url = os.environ.get("STUDIO_TEST_DATABASE_URL", "").strip()
    if not db_url:
        pytest.skip("STUDIO_TEST_DATABASE_URL no definida; omitiendo test contra PostgreSQL vivo.")

    engine = create_engine(db_url, pool_pre_ping=True)
    tenant_id = f"tenant-test-{uuid4().hex[:8]}"
    doc_id = f"doc-test-{uuid4().hex[:8]}"
    user_id = "user-pg-test"

    with Session(engine) as session:
        session.execute(
            text("INSERT INTO public.tenants (tenant_id, name, slug) VALUES (:tid, :name, :slug)"),
            {"tid": tenant_id, "name": "Test Tenant", "slug": tenant_id},
        )
        session.execute(
            text(
                """
                INSERT INTO public.documents (document_id, tenant_id, owner_user_id, filename, mime_type, status)
                VALUES (:doc_id, :tid, :uid, 'contrato.pdf', 'application/pdf', 'PROCESSED')
                """
            ),
            {"doc_id": doc_id, "tid": tenant_id, "uid": user_id},
        )
        session.commit()

        repo = StudioRepositoryPg(session)
        col = repo.create_collection(tenant_id=tenant_id, owner_user_id=user_id, title="Col PG")
        v1 = repo.save_artifact(
            tenant_id=tenant_id,
            owner_user_id=user_id,
            collection_id=col["collection_id"],
            template_id="summary.executive",
            title="Informe v1",
            content={"template_id": "summary.executive", "title": "Informe v1", "body_md": "v1"},
            document_ids=[doc_id],
            groundedness_score=1.0,
        )
        assert v1["version"] == 1

        v2 = repo.save_artifact(
            artifact_id=v1["artifact_id"],
            tenant_id=tenant_id,
            owner_user_id=user_id,
            collection_id=col["collection_id"],
            template_id="summary.executive",
            title="Informe v2",
            content={"template_id": "summary.executive", "title": "Informe v2", "body_md": "v2"},
            document_ids=[doc_id],
            groundedness_score=0.96,
        )
        assert v2["version"] == 2

        versions = repo.list_artifact_versions(
            artifact_id=v1["artifact_id"], tenant_id=tenant_id, owner_user_id=user_id
        )
        assert [row["version_number"] for row in versions] == [2, 1]

        # Updating referenced document must fire trigger -> STALE
        session.execute(
            text("UPDATE public.documents SET updated_at = NOW() WHERE document_id = :doc_id"),
            {"doc_id": doc_id},
        )
        session.commit()

        fetched = repo.get_artifact(
            artifact_id=v1["artifact_id"], tenant_id=tenant_id, owner_user_id=user_id
        )
        assert fetched is not None
        assert fetched["status"] == "STALE"

        # Cleanup
        session.execute(text("DELETE FROM public.tenants WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.commit()
    engine.dispose()
