from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.application.embeddings.use_cases.create_document_embeddings import CreateDocumentEmbeddings
from app.config.settings import get_settings
from app.domain.embeddings import DocumentChunk
from app.infrastructure.database.repositories.document_writer_pg import DocumentWriterPg
from app.infrastructure.database.repositories.vector_repository_pgvector import VectorRepositoryPgVector
from app.interfaces.api.v1 import dependencies
from app.shared.errors import ConflictError, ExternalServiceError, ExtractionError


VECTOR = [1.0] + [0.0] * 383


class RecordingProvider:
    def __init__(self, vector=VECTOR):
        self.vector = vector
        self.batch_sizes = []

    def embed_batch(self, texts):
        self.batch_sizes.append(len(texts))
        return [self.vector] * len(texts)


class RecordingRepository:
    def replace_document_chunks(self, **kwargs):
        self.replacement = kwargs


def test_embedding_batches_and_limits():
    provider = RecordingProvider()
    repository = RecordingRepository()
    creator = CreateDocumentEmbeddings(provider, repository, 1, 0, "fixture-model")
    chunks = creator.execute("fixture", "a" * 65)
    assert provider.batch_sizes == [32, 32, 1]
    assert len(chunks) == len(repository.replacement["vectors"]) == 65
    with pytest.raises(ExtractionError, match="chunk limit"):
        creator.execute("fixture", "a" * 2049)
    with pytest.raises(ExtractionError, match="no extractable text"):
        creator.execute("fixture", " \n ")
    assert provider.batch_sizes == [32, 32, 1]


@pytest.mark.parametrize("vector", [[1.0], [float("nan")] * 384])
def test_invalid_vectors_do_not_replace_chunks(vector):
    repository = RecordingRepository()
    creator = CreateDocumentEmbeddings(RecordingProvider(vector), repository, 10, 0, "fixture-model")
    with pytest.raises(ExternalServiceError, match="invalid vectors"):
        creator.execute("fixture", "synthetic")
    assert not hasattr(repository, "replacement")


@pytest.fixture
def database():
    engine = create_engine(get_settings().database_url)
    marker = uuid4().hex
    try:
        yield engine, marker
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM documents WHERE metadata->>'test_marker' = :marker"), {"marker": marker})
        engine.dispose()


def test_same_document_conflicts_and_retry_keeps_valid_index(database, monkeypatch, tmp_path):
    engine, marker = database
    settings = get_settings().model_copy(update={"document_storage_base_path": str(tmp_path)})
    monkeypatch.setattr(dependencies, "build_embedding_provider", RecordingProvider)
    with Session(engine) as first, Session(engine) as second:
        upload = dependencies.get_upload_document(first, settings)
        document = upload.execute("fixture.txt", "text/plain", BytesIO(b"Synthetic original"), {"test_marker": marker})
        document_id = document.document_id
        writer = DocumentWriterPg(first)
        other = dependencies.build_ingest_existing_document(second, settings)
        with writer.indexing_transaction(document_id):
            with pytest.raises(ConflictError):
                other.execute(document_id)
            assert read_index(second, document_id) == ("PROCESSED", "Synthetic original")

        with pytest.raises(RuntimeError, match="synthetic failure"):
            with writer.indexing_transaction(document_id):
                VectorRepositoryPgVector(first).replace_document_chunks(
                    document_id, [DocumentChunk(document_id, 0, "Partial replacement")], [VECTOR], "fixture-model",
                )
                first.flush()
                raise RuntimeError("synthetic failure")
        assert read_index(second, document_id) == ("PROCESSED", "Synthetic original")

        (tmp_path / document.storage_path).write_text("Synthetic replacement")
        other.execute(document_id)
        assert read_index(second, document_id) == ("PROCESSED", "Synthetic replacement")


def test_initial_index_failure_sets_failed_without_chunks(database, monkeypatch, tmp_path):
    engine, marker = database
    settings = get_settings().model_copy(update={"document_storage_base_path": str(tmp_path)})
    monkeypatch.setattr(dependencies, "build_embedding_provider", lambda: RecordingProvider([1.0]))
    with Session(engine) as session:
        upload = dependencies.get_upload_document(session, settings)
        document = upload.execute(
            "fixture.txt", "text/plain", BytesIO(b"Synthetic fixture"), {"test_marker": marker}, process=False,
        )
        with pytest.raises(ExternalServiceError):
            dependencies.build_ingest_existing_document(session, settings).execute(document.document_id)
        assert read_index(session, document.document_id) == ("FAILED", None)


def read_index(session, document_id):
    return session.execute(text("""
        SELECT documents.status, document_embeddings.chunk_content
        FROM documents LEFT JOIN document_embeddings USING (document_id)
        WHERE document_id = :id
    """), {"id": document_id}).one()
