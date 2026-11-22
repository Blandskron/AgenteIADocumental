"""Deterministic contractual & documentary risk assessor anchored to verified sources (AG-038)."""

from __future__ import annotations

import re
from typing import Any

HIGH_PENALTY_RE = re.compile(r"\b(\d+(?:[.,]\d{1,2})?)\s?%")


def assess_document_risks(
    *,
    comparison: dict[str, Any],
    expirations: dict[str, Any],
) -> dict[str, Any]:
    """Computes a deterministic LOW | MEDIUM | HIGH risk score from verified clauses and dates."""
    findings: list[dict[str, Any]] = []
    score = 0

    summary = expirations.get("summary") or {}
    if int(summary.get("expired") or 0) > 0:
        score += 3
        findings.append(
            {
                "severity": "HIGH",
                "code": "EXPIRED_DATES_DETECTED",
                "message": f"Se detectaron {summary['expired']} fecha(s) vencida(s) en los documentos analizados.",
            }
        )
    if int(summary.get("urgent_30d") or 0) > 0:
        score += 2
        findings.append(
            {
                "severity": "MEDIUM",
                "code": "URGENT_EXPIRATION_30D",
                "message": f"Hay {summary['urgent_30d']} vencimiento(s) dentro de los próximos 30 días.",
            }
        )

    for doc in comparison.get("documents") or []:
        clauses = doc.get("clauses") or {}
        filename = str(doc.get("filename") or doc.get("document_id") or "")
        if "penalizacion" in clauses:
            for item in clauses["penalizacion"]:
                for match in HIGH_PENALTY_RE.findall(str(item.get("quote") or "")):
                    val = float(match.replace(",", "."))
                    if val >= 5.0:
                        score += 2
                        findings.append(
                            {
                                "severity": "HIGH",
                                "code": "HIGH_PENALTY_RATE",
                                "message": f"Penalización elevada ({val}%) detectada en {filename} [Fuente {item.get('source_index')}].",
                            }
                        )
        if not clauses.get("rescision") and comparison.get("documents_compared", 0) >= 1:
            score += 1
            findings.append(
                {
                    "severity": "LOW",
                    "code": "MISSING_TERMINATION_CLAUSE",
                    "message": f"No se detectó cláusula explícita de rescisión/preaviso en {filename}.",
                }
            )

    if score >= 4:
        level = "HIGH"
    elif score >= 2:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "risk_level": level,
        "risk_score": score,
        "findings": findings,
    }
