from __future__ import annotations

import pytest

from app.application.templates.agent_templates import (
    extract_deterministic_facts,
    get_agent_template,
    list_agent_templates,
)


def test_agent_templates_catalog_and_validation() -> None:
    templates = list_agent_templates()
    ids = {t["template_id"] for t in templates}
    assert {
        "research_general",
        "contract_comparison",
        "dates_amounts_extraction",
        "executive_report_studio",
    }.issubset(ids)

    exec_tpl = get_agent_template("executive_report_studio")
    assert exec_tpl.default_save_to_studio is True

    default_tpl = get_agent_template(None)
    assert default_tpl.template_id == "research_general"

    with pytest.raises(ValueError):
        get_agent_template("non_existent_template")


def test_deterministic_date_and_amount_extraction() -> None:
    evidence = [
        {
            "document_id": "doc-1",
            "chunk_index": 3,
            "quote": "Vencimiento 2027-06-30, importe USD 14,500.00 y recargo del 2.5% mensual.",
        },
        {
            "document_id": "doc-2",
            "chunk_index": 1,
            "quote": "Fecha de firma 15/01/2026 con garantía de $5000.",
        },
    ]
    facts = extract_deterministic_facts(evidence)
    date_values = {d["value"] for d in facts["dates"]}
    amount_values = {a["value"] for a in facts["amounts"]}

    assert "2027-06-30" in date_values
    assert "15/01/2026" in date_values
    assert any("14,500.00" in a for a in amount_values)
    assert any("2.5%" in a for a in amount_values)
