"""Deterministic expiration & deadline detector anchored to verified sources (AG-027)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.application.templates.agent_templates import ISO_DATE_RE, LATAM_DATE_RE


def _parse_date(raw: str) -> date | None:
    text = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _classify_urgency(days_remaining: int) -> str:
    if days_remaining < 0:
        return "EXPIRED"
    if days_remaining <= 30:
        return "URGENT_30D"
    if days_remaining <= 90:
        return "UPCOMING_90D"
    return "FUTURE"


def detect_expirations(
    sources: list[dict[str, Any]],
    *,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """Extracts dates from verified sources, computes days remaining and classifies urgency."""
    today = reference_date or datetime.now(timezone.utc).date()
    alerts: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()

    for idx, src in enumerate(sources, start=1):
        quote = str(src.get("quote") or "")
        doc_id = str(src.get("document_id") or "")
        chunk_idx = int(src.get("chunk_index") or 0)
        filename = str(src.get("filename") or doc_id)
        source_index = int(src.get("source_index") or idx)

        raw_dates = list(ISO_DATE_RE.findall(quote)) + list(LATAM_DATE_RE.findall(quote))
        for raw in raw_dates:
            parsed = _parse_date(raw)
            if parsed is None:
                continue
            iso_val = parsed.isoformat()
            dedup_key = (doc_id, chunk_idx, iso_val)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            days_remaining = (parsed - today).days
            alerts.append(
                {
                    "date": iso_val,
                    "raw_date": raw,
                    "days_remaining": days_remaining,
                    "urgency": _classify_urgency(days_remaining),
                    "document_id": doc_id,
                    "chunk_index": chunk_idx,
                    "filename": filename,
                    "source_index": source_index,
                    "quote": quote[:200],
                }
            )

    alerts.sort(key=lambda item: item["days_remaining"])
    summary = {
        "expired": sum(1 for a in alerts if a["urgency"] == "EXPIRED"),
        "urgent_30d": sum(1 for a in alerts if a["urgency"] == "URGENT_30D"),
        "upcoming_90d": sum(1 for a in alerts if a["urgency"] == "UPCOMING_90D"),
        "future": sum(1 for a in alerts if a["urgency"] == "FUTURE"),
    }
    return {
        "reference_date": today.isoformat(),
        "total_dates": len(alerts),
        "summary": summary,
        "alerts": alerts,
    }
