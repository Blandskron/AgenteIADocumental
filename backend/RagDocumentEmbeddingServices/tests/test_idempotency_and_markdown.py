from io import BytesIO
from pathlib import Path

from app.application.documents.use_cases.upload_document import UploadDocument
from app.domain.documents import Document, DocumentStatus
from app.infrastructure.extractors.markdown_normalizer import is_ignored_vault_path, normalize_markdown
from app.infrastructure.storage.document_storage import LocalDocumentStorage


class _InMemoryWriter:
    def __init__(self):
        self.docs: list[Document] = []

    def create(self, filename, storage_path, mime_type, metadata=None, status="PENDING"):
        doc = Document(
            document_id=f"doc-{len(self.docs) + 1}",
            filename=filename,
            storage_path=storage_path,
            mime_type=mime_type,
            status=DocumentStatus(status),
            metadata=metadata or {},
            owner_user_id=(metadata or {}).get("owner_user_id"),
            tenant_id=(metadata or {}).get("tenant_id"),
        )
        self.docs.append(doc)
        return doc

    def find_existing_idempotent(self, owner_user_id, tenant_id, idempotency_key=None, content_sha256=None):
        for doc in self.docs:
            if doc.owner_user_id != owner_user_id or doc.tenant_id != tenant_id:
                continue
            if idempotency_key and doc.metadata.get("idempotency_key") == idempotency_key:
                return doc
            if content_sha256 and doc.metadata.get("content_sha256") == content_sha256:
                return doc
        return None


class _NoOpIngestion:
    def __init__(self):
        self.calls = 0

    def execute(self, _document_id):
        self.calls += 1


def test_upload_idempotency_and_normalized_source_metadata(tmp_path):
    writer = _InMemoryWriter()
    storage = LocalDocumentStorage(str(tmp_path))
    ingestion = _NoOpIngestion()
    use_case = UploadDocument(writer, storage, ingestion)

    meta = {"owner_user_id": "42", "tenant_id": "tenant-1"}
    payload = b"Contenido sintetico de prueba idempotente."
    first = use_case.execute("nota.txt", "text/plain", BytesIO(payload), metadata=meta, idempotency_key="idem-001")
    second = use_case.execute("nota.txt", "text/plain", BytesIO(payload), metadata=meta, idempotency_key="idem-001")

    assert first.document_id == second.document_id
    assert len(writer.docs) == 1
    assert ingestion.calls == 1
    assert first.metadata["content_sha256"]
    assert first.metadata["source"]["sha256"] == first.metadata["content_sha256"]
    assert first.metadata["source"]["kind"] == "upload"
    assert first.metadata["idempotency_key"] == "idem-001"


def test_markdown_normalizer_parses_frontmatter_wikilinks_tags_and_ignores_obsidian(tmp_path):
    sample = (
        "---\n"
        "title: Arquitectura del Modulo de Custodia\n"
        "tags: [arquitectura, custodia]\n"
        "aliases: [Custodia-Core]\n"
        "---\n\n"
        "# Arquitectura\n\n"
        "Delega en [[Politica-Rotacion-Claves]] y [[Registro-Auditoria-Interna|Auditoria]].\n"
        "Ver tambien [Guia](./guia.md). #seguridad\n"
    )
    parsed = normalize_markdown(sample)
    assert parsed.frontmatter["title"] == "Arquitectura del Modulo de Custodia"
    assert parsed.frontmatter["aliases"] == ["Custodia-Core"]
    assert parsed.wikilinks == ["Politica-Rotacion-Claves", "Registro-Auditoria-Interna"]
    assert parsed.markdown_links == ["./guia.md"]
    assert parsed.tags == ["arquitectura", "custodia", "seguridad"]
    assert "title:" not in parsed.clean_text
    assert "Politica-Rotacion-Claves" in parsed.clean_text
    assert "Auditoria" in parsed.clean_text
    assert "[[" not in parsed.clean_text

    assert is_ignored_vault_path(".obsidian/workspace.json") is True
    assert is_ignored_vault_path("vault/.trash/old.md") is True
    assert is_ignored_vault_path("vault/notas/arquitectura.md") is False

    # Upload stores parsed markdown metadata on the document.
    writer = _InMemoryWriter()
    storage = LocalDocumentStorage(str(tmp_path))
    use_case = UploadDocument(writer, storage, _NoOpIngestion())
    doc = use_case.execute(
        "arquitectura.md",
        "text/markdown",
        BytesIO(sample.encode("utf-8")),
        metadata={"owner_user_id": "42", "tenant_id": "t1"},
        process=False,
    )
    assert doc.metadata["markdown"]["wikilinks"] == ["Politica-Rotacion-Claves", "Registro-Auditoria-Interna"]
    assert "seguridad" in doc.metadata["markdown"]["tags"]
    assert Path(tmp_path, doc.storage_path).is_file()

