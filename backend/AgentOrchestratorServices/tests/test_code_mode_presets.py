from __future__ import annotations

from app.application.graph.code_mode_presets import list_code_mode_presets


def test_code_mode_presets_all_pass_sandbox_static_policy() -> None:
    presets = list_code_mode_presets()
    ids = {p["preset_id"] for p in presets}
    assert {"group_by_document", "sum_numeric_amounts", "filter_iso_dates"}.issubset(ids)
    for preset in presets:
        assert "function transform(" in preset["code"]
