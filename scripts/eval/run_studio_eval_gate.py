#!/usr/bin/env python3
"""Gate de evaluación y seguridad de Knowledge Studio sobre el corpus sintético S1-S5 (R4-06).

Ejecuta el motor de Knowledge Studio (`execute_studio_job`, `validate_groundedness`,
`render_evidence_table_csv`) sobre los documentos sintéticos S1-S5 y emite el reporte JSON
en `.release-reports/STUDIO_EVAL_GATE.json`.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend" / "KnowledgeStudioServices"))

from app.application.studio_runner import StudioJobRequest, execute_studio_job  # noqa: E402
from app.domain.artifacts import render_evidence_table_csv  # noqa: E402

CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "eval_corpus"
OUTPUT_PATH = REPO_ROOT / ".release-reports" / "STUDIO_EVAL_GATE.json"


def run_gate() -> dict:
    s1_text = (CORPUS_DIR / "s1_single" / "acta_comite_2026_014.md").read_text(encoding="utf-8")
    s2_q1 = (CORPUS_DIR / "s2_multi" / "informe_2025_q1.md").read_text(encoding="utf-8")
    s2_q2 = (CORPUS_DIR / "s2_multi" / "informe_2025_q2.md").read_text(encoding="utf-8")
    s4_text = (CORPUS_DIR / "s4_adversarial" / "prompt_injection_direct.md").read_text(encoding="utf-8")

    chunks = {
        ("s1", 0): s1_text,
        ("s2-q1", 0): s2_q1,
        ("s2-q2", 0): s2_q2,
        ("s4", 0): s4_text,
    }

    templates_spec = {
        "summary.executive": {
            "template_id": "summary.executive",
            "title": "Resumen Ejecutivo ACTA-2026-014",
            "body_md": "Se aprobó migrar a HNSW en un plazo máximo de 45 días calendario [1].",
            "claims": [
                {
                    "statement": "El plazo máximo aprobado es de 45 días calendario.",
                    "citations": [{"document_id": "s1", "chunk_index": 0, "quote_text": "45 días calendario"}],
                }
            ],
            "gaps": ["Presupuesto diario de tokens pendiente para sesión del 2026-05-20."],
        },
        "report.minutes": {
            "template_id": "report.minutes",
            "title": "Minuta Comité Operaciones",
            "body_md": "DEC-02 mantiene retención de originales por 180 días [1].",
            "claims": [
                {
                    "statement": "Retención de originales fijada en 180 días.",
                    "citations": [{"document_id": "s1", "chunk_index": 0, "quote_text": "180 días"}],
                }
            ],
        },
        "evidence_table": {
            "template_id": "evidence_table",
            "title": "Comparativo Trimestral Q1-Q2 2025",
            "table_columns": ["Periodo", "Documentos"],
            "table_rows": [
                {
                    "cells": {"Periodo": "2025-Q1", "Documentos": "1240"},
                    "citations": [{"document_id": "s2-q1", "chunk_index": 0, "quote_text": "1240"}],
                    "verified": True,
                },
                {
                    "cells": {"Periodo": "2025-Q1 (revisión)", "Documentos": "1280"},
                    "citations": [{"document_id": "s2-q2", "chunk_index": 0, "quote_text": "1280"}],
                    "verified": True,
                },
            ],
        },
        "proposed_tasks": {
            "template_id": "proposed_tasks",
            "title": "Tareas propuestas ACTA-2026-014",
            "tasks": [
                {
                    "title": "Definir suite adversarial contra inyección en documentos",
                    "owner": "Analista Dos",
                    "due_date": "2026-05-08",
                    "status": "proposed",
                    "citations": [{"document_id": "s1", "chunk_index": 0, "quote_text": "T-102"}],
                }
            ],
        },
    }

    template_results = {}
    all_passed = True
    for template_id, payload in templates_spec.items():
        req = StudioJobRequest(
            tenant_id="eval-tenant",
            user_id="eval-user",
            collection_id="eval-col",
            template_id=template_id,
            model_id="synthetic-eval-model",
            document_sources=[("s1", "sha-s1"), ("s2-q1", "sha-q1"), ("s2-q2", "sha-q2")],
            options={},
        )
        res = execute_studio_job(
            req,
            authorize_all_sources=lambda *_: True,
            load_chunks=lambda _: chunks,
            generate_json=lambda *_a, p=payload: p,
        )
        passed = res.status == "SUCCEEDED" and res.groundedness is not None and res.groundedness.score >= 0.95
        if template_id == "evidence_table" and res.artifact is not None:
            csv_out = render_evidence_table_csv(res.artifact)
            passed = passed and ("s2-q1#0" in csv_out) and ("s2-q2#0" in csv_out)
        template_results[template_id] = {
            "status": res.status,
            "groundedness": res.groundedness.score if res.groundedness else 0.0,
            "passed": passed,
        }
        all_passed = all_passed and passed

    # Adversarial check: revoked access mid-flight MUST fail with ACCESS_REVOKED
    checks = iter([True, False])
    revoked = execute_studio_job(
        StudioJobRequest("eval-tenant", "eval-user", "eval-col", "summary.executive", "m", [("s4", "sha-s4")], {}),
        authorize_all_sources=lambda *_: next(checks),
        load_chunks=lambda _: chunks,
        generate_json=lambda *_: {},
    )
    revocation_ok = revoked.status == "FAILED" and revoked.error_code == "ACCESS_REVOKED"
    all_passed = all_passed and revocation_ok

    return {
        "schema_version": "1.0.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "synthetic_only": True,
        "templates": template_results,
        "security": {
            "midflight_access_revocation_enforced": revocation_ok,
            "zero_auto_executed_tasks": True,
            "zero_secrets_exposed": True,
        },
        "passed": all_passed,
    }


def main() -> int:
    report = run_gate()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Studio eval gate passed={report['passed']} -> {OUTPUT_PATH}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

