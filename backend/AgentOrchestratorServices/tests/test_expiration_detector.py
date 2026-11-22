from __future__ import annotations

from datetime import date

from app.application.analysis.expiration_detector import detect_expirations


def test_expiration_detector_classifies_urgency_buckets_and_deduplicates() -> None:
    sources = [
        {
            "source_index": 1,
            "document_id": "doc-1",
            "chunk_index": 0,
            "filename": "p1.pdf",
            "quote": "Vencimiento vencido 2026-10-01 y renovación urgente 05/12/2026.",
        },
        {
            "source_index": 2,
            "document_id": "doc-2",
            "chunk_index": 1,
            "filename": "p2.pdf",
            "quote": "Próximo hito 2027-01-15 y cierre final 2027-09-01.",
        },
    ]

    report = detect_expirations(sources, reference_date=date(2026, 11, 22))
    assert report["total_dates"] == 4
    assert report["summary"] == {"expired": 1, "urgent_30d": 1, "upcoming_90d": 1, "future": 1}
    urgencies = [a["urgency"] for a in report["alerts"]]
    assert urgencies == ["EXPIRED", "URGENT_30D", "UPCOMING_90D", "FUTURE"]
