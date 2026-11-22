from __future__ import annotations

from app.application.analysis.contract_comparator import compare_contract_clauses


def test_contract_comparator_detects_differences_and_renders_cited_table() -> None:
    sources = [
        {
            "source_index": 1,
            "document_id": "doc-a",
            "filename": "contrato_alpha.pdf",
            "quote": "Cláusula de penalización del 2.5% mensual por mora. Vigencia hasta 2027-06-30.",
        },
        {
            "source_index": 2,
            "document_id": "doc-b",
            "filename": "contrato_beta.pdf",
            "quote": "Cláusula de confidencialidad NDA. Monto mensual USD 4,500.00. Vencimiento 2027-12-31.",
        },
    ]

    result = compare_contract_clauses(sources)
    assert result["documents_compared"] == 2
    diff_categories = {d["category"] for d in result["differences"]}
    assert "penalizacion" in diff_categories
    assert "confidencialidad" in diff_categories
    assert "| contrato_alpha.pdf |" in result["comparison_markdown"]
    assert "[Fuente 1]" in result["comparison_markdown"]
    assert "[Fuente 2]" in result["comparison_markdown"]
