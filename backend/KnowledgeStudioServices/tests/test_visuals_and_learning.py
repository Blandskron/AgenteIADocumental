from app.domain.artifacts import ArtifactContent, Citation, EvidenceRow
from app.domain.visuals_and_learning import (
    FlashcardState,
    QuizQuestion,
    build_concept_graph_from_wikilinks,
    extract_verified_chart_series,
    filter_valid_quiz_questions,
    sanitize_mermaid_diagram,
    sm2_review,
)


def test_deterministic_visualizations_and_mermaid_sanitization():
    assert sanitize_mermaid_diagram("flowchart LR\n  A --> B").startswith("flowchart LR")
    for unsafe in (
        "flowchart LR\n  A[<script>alert(1)</script>]",
        "flowchart LR\n  A[<foreignObject>x</foreignObject>]",
        "flowchart LR\n  click A href \"https://evil.invalid\"",
    ):
        try:
            sanitize_mermaid_diagram(unsafe)
            raise AssertionError("Expected ValueError for unsafe Mermaid")
        except ValueError:
            pass

    graph = build_concept_graph_from_wikilinks([
        {"document_id": "d1", "title": "Custodia", "wikilinks": ["Rotacion"]},
    ])
    assert len(graph["nodes"]) == 2
    assert graph["edges"] == [{"source": "d1", "target": "ref:Rotacion"}]

    table = ArtifactContent(
        template_id="evidence_table",
        title="Latencia",
        table_columns=["Periodo", "p95"],
        table_rows=[
            EvidenceRow(
                cells={"Periodo": "2026-Q1", "p95": "215"},
                citations=[Citation(document_id="s2", chunk_index=0, quote_text="215 ms")],
                verified=True,
            ),
            EvidenceRow(
                cells={"Periodo": "2026-Q2", "p95": "999"},
                citations=[],
                verified=False,
            ),
        ],
    )
    series = extract_verified_chart_series(table, "Periodo", "p95")
    assert len(series) == 1
    assert series[0].label == "2026-Q1" and series[0].value == 215.0 and series[0].provenance == "s2#0"


def test_quiz_validator_and_offline_sm2_spaced_repetition():
    chunks = {("s1", 0): "La retencion de originales es de 180 dias tras el archivado."}
    q_ok = QuizQuestion(
        prompt="Cuantos dias se retienen los originales?",
        options=["90 dias", "180 dias", "365 dias"],
        correct_index=1,
        explanation="DEC-02 establece 180 dias.",
        citations=[Citation(document_id="s1", chunk_index=0, quote_text="180 dias")],
    )
    q_bad = QuizQuestion(
        prompt="Pregunta sin sustento?",
        options=["A", "B"],
        correct_index=0,
        explanation="Cita falsa.",
        citations=[Citation(document_id="s1", chunk_index=0, quote_text="texto inexistente")],
    )
    filtered = filter_valid_quiz_questions([q_ok, q_bad], chunks)
    assert len(filtered) == 1 and filtered[0].prompt == q_ok.prompt

    card = FlashcardState(card_id="c1", front="Retencion?", back="180 dias")
    r1 = sm2_review(card, 5)
    assert r1.repetitions == 1 and r1.interval_days == 1
    r2 = sm2_review(r1, 5)
    assert r2.repetitions == 2 and r2.interval_days == 6
    r_fail = sm2_review(r2, 1)
    assert r_fail.repetitions == 0 and r_fail.interval_days == 1
