"""Unit tests for EVO-014 document versioning diff, tag normalization, and shared folder visibility."""

from __future__ import annotations

import pytest

from app.domain.versioning_and_tags import (
    compute_version_diff,
    normalize_tag_name,
    validate_folder_visibility,
    validate_tag_color,
)


def test_deterministic_version_diff() -> None:
    v1 = "Clausula 1: Plazo de 30 dias.\nClausula 2: Multa 5%."
    v2 = "Clausula 1: Plazo de 45 dias.\nClausula 2: Multa 5%.\nClausula 3: Renovacion automatica."

    diff = compute_version_diff(v1, v2, from_label="v1", to_label="v2")
    assert diff.identical is False
    assert diff.added_lines == 2
    assert diff.removed_lines == 1
    assert "+Clausula 1: Plazo de 45 dias." in diff.unified_diff

    same = compute_version_diff(v1, v1)
    assert same.identical is True
    assert same.unified_diff == ""


def test_tag_and_folder_visibility_validation() -> None:
    assert normalize_tag_name("  Legal   Contratos ") == "Legal Contratos"
    assert validate_tag_color("emerald") == "emerald"
    assert validate_folder_visibility("area", "area-legal") == ("area", "area-legal")
    assert validate_folder_visibility("company", "area-ignored") == ("company", None)

    with pytest.raises(ValueError):
        normalize_tag_name("   ")
    with pytest.raises(ValueError):
        validate_tag_color("neon-invalid")
    with pytest.raises(ValueError):
        validate_folder_visibility("area", None)
