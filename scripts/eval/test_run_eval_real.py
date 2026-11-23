"""Unit tests for scripts/eval/run_eval_real.py IR/RAG metrics and refusal detection (EVO-011)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

_MOD_PATH = Path(__file__).resolve().parent / "run_eval_real.py"
_SPEC = importlib.util.spec_from_file_location("run_eval_real", _MOD_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["run_eval_real"] = _MOD
_SPEC.loader.exec_module(_MOD)


def test_ir_metrics_math() -> None:
    retrieved = ["d2", "d1", "d3", "d4", "d5"]
    relevant = {"d1", "d3"}

    assert _MOD.recall_at_k(retrieved, relevant, 5) == 1.0
    assert _MOD.precision_at_k(retrieved, relevant, 5) == 0.4
    assert _MOD.reciprocal_rank(retrieved, relevant) == 0.5
    ndcg = _MOD.ndcg_at_k(retrieved, relevant, 5)
    assert 0.65 < ndcg < 0.80


def test_citation_accuracy_and_refusal_detection() -> None:
    assert _MOD.citation_accuracy("Dato [Fuente 1] y [Fuente 2].", 2) == 1.0
    assert _MOD.citation_accuracy("Dato [Fuente 1] y [Fuente 9].", 2) == 0.5
    assert _MOD.is_refusal_answer("No encontré evidencia suficiente en los documentos.", "ok") is True
    assert _MOD.is_refusal_answer("Cualquier texto", "insufficient_evidence") is True
    assert _MOD.is_refusal_answer("El plazo es de 30 días [Fuente 1].", "ok") is False
