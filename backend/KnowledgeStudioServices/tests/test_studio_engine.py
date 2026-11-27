"""Tests for Knowledge Studio P0 schemas, groundedness validator, CSV safety, and access revocation (R4-02, R4-03)."""

from app.application.studio_runner import StudioJobRequest, execute_studio_job
from app.domain.artifacts import (
    ArtifactContent,
    Citation,
    EvidenceRow,
    FactualClaim,
    render_evidence_table_csv,
    validate_groundedness,
)


CHUNKS = {
    ("doc-s1", 0): "El comité aprobó migrar a HNSW con un plazo máximo de 45 días calendario.",
    ("doc-s2", 0): "En Q1 2025 hubo 1240 documentos indexados y en Q1 2026 la latencia p95 bajó a 215 ms.",
}


def test_groundedness_accepts_anchored_claims_and_rejects_hallucinated_quotes():
    valid_artifact = ArtifactContent(
        template_id="summary.executive",
        title="Resumen Ejecutivo",
        body_md="El plazo es de 45 días [1].",
        claims=[
            FactualClaim(
                statement="El plazo máximo aprobado es de 45 días calendario.",
                citations=[Citation(document_id="doc-s1", chunk_index=0, quote_text="plazo máximo de 45 días calendario")],
            )
        ],
    )
    ok = validate_groundedness(valid_artifact, CHUNKS)
    assert ok.valid is True
    assert ok.score == 1.0

    bad_artifact = ArtifactContent(
        template_id="summary.executive",
        title="Resumen con alucinación",
        claims=[
            FactualClaim(
                statement="El presupuesto aprobado fue de 9 millones.",
                citations=[Citation(document_id="doc-s1", chunk_index=0, quote_text="presupuesto de 9 millones")],
            )
        ],
    )
    bad = validate_groundedness(bad_artifact, CHUNKS)
    assert bad.valid is False
    assert bad.score == 0.0

    empty_claims_artifact = ArtifactContent(
        template_id="summary.executive",
        title="Resumen vacío",
        body_md="Sin afirmaciones citadas.",
        claims=[],
    )
    empty_report = validate_groundedness(empty_claims_artifact, CHUNKS)
    assert empty_report.valid is False
    assert empty_report.score == 0.0
    assert any("factual claim" in err for err in empty_report.errors)


def test_evidence_table_csv_neutralizes_formula_injection_and_keeps_provenance():
    artifact = ArtifactContent(
        template_id="evidence_table",
        title="Tabla Q1",
        table_columns=["Periodo", "FormulaTest"],
        table_rows=[
            EvidenceRow(
                cells={"Periodo": "2026-Q1", "FormulaTest": "=CMD|' /C calc'!A0"},
                citations=[Citation(document_id="doc-s2", chunk_index=0, quote_text="latencia p95 bajó a 215 ms")],
                verified=True,
            )
        ],
    )
    csv_text = render_evidence_table_csv(artifact)
    assert "'=CMD|" in csv_text
    assert "doc-s2#0" in csv_text


def test_studio_runner_enforces_midflight_access_revocation_and_single_repair():
    req = StudioJobRequest(
        tenant_id="t1",
        user_id="42",
        collection_id="col-1",
        template_id="summary.executive",
        model_id="llama-3.3-70b-versatile",
        document_sources=[("doc-s1", "sha-1")],
        options={},
    )

    # Mid-flight revocation: first check True, second check False -> ACCESS_REVOKED
    checks = iter([True, False])
    revoked = execute_studio_job(
        req,
        authorize_all_sources=lambda *_: next(checks),
        load_chunks=lambda _: CHUNKS,
        generate_json=lambda *_: {},
    )
    assert revoked.status == "FAILED"
    assert revoked.error_code == "ACCESS_REVOKED"

    # Bounded 1-attempt repair: first returns unanchored quote, second returns anchored quote -> SUCCEEDED
    attempts = []

    def generate(_req, _chunks, repair_errors):
        attempts.append(repair_errors)
        if len(attempts) == 1:
            return {
                "template_id": "summary.executive",
                "title": "Intento 1",
                "claims": [{"statement": "Dato inventado", "citations": []}],
            }
        return {
            "template_id": "summary.executive",
            "title": "Intento 2 reparado",
            "claims": [
                {
                    "statement": "Plazo máximo de 45 días.",
                    "citations": [{"document_id": "doc-s1", "chunk_index": 0, "quote_text": "plazo máximo de 45 días"}],
                }
            ],
        }

    repaired = execute_studio_job(
        req,
        authorize_all_sources=lambda *_: True,
        load_chunks=lambda _: CHUNKS,
        generate_json=generate,
    )
    assert repaired.status == "SUCCEEDED"
    assert len(attempts) == 2
    assert repaired.groundedness is not None and repaired.groundedness.score == 1.0

