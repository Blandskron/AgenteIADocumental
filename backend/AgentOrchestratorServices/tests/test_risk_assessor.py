from __future__ import annotations

from datetime import date

from app.application.analysis.contract_comparator import compare_contract_clauses
from app.application.analysis.expiration_detector import detect_expirations
from app.application.analysis.risk_assessor import assess_document_risks


def test_risk_assessor_flags_expired_dates_high_penalties_and_missing_clauses() -> None:
    sources = [
        {
            "source_index": 1,
            "document_id": "doc-risk",
            "chunk_index": 0,
            "filename": "contrato_riesgoso.pdf",
            "quote": "Penalización del 8.5% mensual por mora. Vencimiento 2026-09-01.",
        }
    ]
    comparison = compare_contract_clauses(sources)
    expirations = detect_expirations(sources, reference_date=date(2026, 11, 22))
    risk = assess_document_risks(comparison=comparison, expirations=expirations)

    assert risk["risk_level"] == "HIGH"
    codes = {f["code"] for f in risk["findings"]}
    assert "EXPIRED_DATES_DETECTED" in codes
    assert "HIGH_PENALTY_RATE" in codes
    assert "MISSING_TERMINATION_CLAUSE" in codes
