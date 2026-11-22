from __future__ import annotations

from app.application.export_service import export_run_csv, export_run_markdown


def test_export_run_markdown_and_formula_safe_csv() -> None:
    run = {
        "run_id": "run_abc123",
        "goal": "Extraer vencimientos",
        "status": "SUCCEEDED",
        "provider": "ollama",
        "steps_used": 2,
        "usage_tokens": 850,
        "result_markdown": "El contrato vence el 2027-06-30 [Fuente 1].",
        "sources": [
            {
                "document_id": "doc-1",
                "chunk_index": 4,
                "filename": "contrato.pdf",
                "quote": "=HYPERLINK(\"http://evil\",\"click\") vencimiento 2027-06-30",
            }
        ],
    }

    md = export_run_markdown(run)
    assert "# Informe Agente Documental — run_abc123" in md
    assert "[Fuente 1]" in md
    assert "doc-1#4" in md

    csv_out = export_run_csv(run)
    assert "run_id,source_index,document_id,chunk_index,filename,quote" in csv_out
    assert "'=HYPERLINK" in csv_out
