from app.infrastructure.pdf.renderer_registry import build_default_registry


def test_renderer_registry_preserves_chat_message_and_renders_studio_artifact():
    registry = build_default_registry(chat_pdf_renderer=lambda payload: b"%PDF-1.4-" + payload["title"].encode())
    assert registry.supported_types() == ("chat_message", "studio_artifact")

    pdf_bytes = registry.render("chat_message", {"title": "Chat1"})
    assert pdf_bytes == b"%PDF-1.4-Chat1"

    md_bytes = registry.render(
        "studio_artifact",
        {
            "title": "Resumen Ejecutivo",
            "template_id": "summary.executive",
            "body_md": "El plazo aprobado es de 45 dias [1].",
            "gaps": ["Presupuesto diario de tokens pendiente."],
            "sources": [{"document_id": "doc-s1", "chunk_index": 0}],
        },
    )
    text = md_bytes.decode("utf-8")
    assert "# Resumen Ejecutivo" in text
    assert "`summary.executive`" in text
    assert "Vacíos de información" in text
    assert "`doc-s1` (fragmento #0)" in text

