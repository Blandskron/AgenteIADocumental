from app.application.embeddings.use_cases.create_document_embeddings import CreateDocumentEmbeddings

VECTOR = [1.0] + [0.0] * 383


class _RecordingProvider:
    def embed_batch(self, texts):
        return [VECTOR] * len(texts)


class _RecordingRepository:
    def __init__(self):
        self.chunks = []

    def replace_document_chunks(self, **kwargs):
        self.chunks = kwargs["chunks"]


def test_pdf_page_markers_become_structured_metadata_without_polluting_chunks():
    repo = _RecordingRepository()
    creator = CreateDocumentEmbeddings(_RecordingProvider(), repo, chunk_size=300, chunk_overlap=40, embedding_model="e5")
    text = (
        "[page 1]\n# Resumen ejecutivo\n\nEl plazo del contrato es de 45 dias calendario.\n\n"
        "[page 2]\n## Acuerdos\n\nLa retencion de originales es de 180 dias."
    )
    chunks = creator.execute("doc-pdf", text, metadata={"tenant_id": "t1"})
    assert len(chunks) == 2

    assert chunks[0].metadata == {"tenant_id": "t1", "page": 1, "section": "Resumen ejecutivo"}
    assert "[page 1]" not in chunks[0].content
    assert "45 dias" in chunks[0].content

    assert chunks[1].metadata == {"tenant_id": "t1", "page": 2, "section": "Acuerdos"}
    assert "[page 2]" not in chunks[1].content
    assert "180 dias" in chunks[1].content


def test_sentence_and_section_boundaries_avoid_mid_sentence_splits():
    repo = _RecordingRepository()
    creator = CreateDocumentEmbeddings(_RecordingProvider(), repo, chunk_size=140, chunk_overlap=25, embedding_model="e5")
    text = (
        "Primera oracion completa sobre politicas de archivo documental. "
        "Segunda oracion completa sobre validacion de permisos multiempresa. "
        "Tercera oracion completa sobre generacion de embeddings locales en CPU."
    )
    chunks = creator.execute("doc-sentences", text)
    assert len(chunks) >= 2
    assert all(len(chunk.content) <= 140 for chunk in chunks)
    # First chunk ends cleanly at a sentence boundary.
    assert chunks[0].content.endswith(".")


def test_markdown_headings_split_sections_and_preserve_section_metadata():
    repo = _RecordingRepository()
    creator = CreateDocumentEmbeddings(_RecordingProvider(), repo, chunk_size=400, chunk_overlap=50, embedding_model="e5")
    text = (
        "# Acta Comite\n\n"
        "Resumen inicial de operaciones sinteticas.\n\n"
        "## Decisiones\n\n"
        "DEC-01 migrar a HNSW.\n\n"
        "## Glosario\n\n"
        "Recall@K mide fragmentos relevantes."
    )
    chunks = creator.execute("doc-md", text)
    sections = [chunk.metadata["section"] for chunk in chunks]
    assert sections == ["Acta Comite", "Decisiones", "Glosario"]

