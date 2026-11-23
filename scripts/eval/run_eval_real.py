#!/usr/bin/env python3
"""Runner reproducible de evaluación RAG real (EVO-011).

Calcula métricas IR y RAG estándar:
  - Recall@5, Recall@10, Precision@5, MRR, NDCG@5
  - Exactitud de citas ([Fuente N] ancladas a fuentes retornadas)
  - Tasa de rechazo en preguntas sin respuesta (S6-S8)

Modos de ejecución:
  1. Live HTTP contra RagDocumentChatServices (`--chat-url` + `--token`), ejercitando
     PostgreSQL 16 + pgvector HNSW + FTS + RRF + multilingual-e5-small + LLM reales.
  2. Evaluación local sobre `tests/fixtures/eval_corpus/ground_truth.json` (sin servicios
     externos) para validar métricas y contrato de reporte en entornos aislados.

Emite un reporte JSON fechado en `.release-reports/RAG_REAL_EVAL.json`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from typing import Any
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "eval_corpus"
DEFAULT_OUTPUT = REPO_ROOT / ".release-reports" / "RAG_REAL_EVAL.json"

CITATION_RE = re.compile(r"\[Fuente\s+(\d+)\]", re.IGNORECASE)
REFUSAL_MARKERS = (
    "no encontre evidencia",
    "no encontré evidencia",
    "no hay evidencia",
    "no contiene la respuesta",
    "no se menciona",
    "no dispongo de informacion",
    "no dispongo de información",
    "evidencia suficiente",
)

UNANSWERABLE_PROBES: tuple[dict[str, str], ...] = (
    {"id": "S6-unanswerable-1", "question": "¿Cuál fue el dividendo exacto aprobado para el ejercicio 2049 en Marte?"},
    {"id": "S7-unanswerable-2", "question": "¿Qué número de pasaporte personal figura en la cláusula 99 del anexo secreto?"},
    {"id": "S8-unanswerable-3", "question": "¿Cuál es la contraseña maestra de producción mencionada en los contratos?"},
)


@dataclass(frozen=True)
class Thresholds:
    min_recall_at_5: float = 0.60
    min_mrr: float = 0.50
    min_ndcg_at_5: float = 0.50
    min_refusal_rate: float = 0.66


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 1.0
    top_k = retrieved[:k]
    hits = sum(1 for item in set(top_k) if item in relevant)
    return hits / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for item in top_k if item in relevant)
    return hits / len(top_k)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant or k <= 0:
        return 0.0
    dcg = 0.0
    for idx, item in enumerate(retrieved[:k], start=1):
        if item in relevant:
            dcg += 1.0 / math.log2(idx + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, ideal_hits + 1))
    return (dcg / idcg) if idcg > 0 else 0.0


def citation_accuracy(answer: str, source_count: int) -> float:
    found = [int(m.group(1)) for m in CITATION_RE.finditer(answer or "")]
    if not found:
        return 0.0 if source_count > 0 else 1.0
    valid = sum(1 for num in found if 1 <= num <= source_count)
    return valid / len(found)


def is_refusal_answer(answer: str, provider_status: str = "ok") -> bool:
    if provider_status == "insufficient_evidence":
        return True
    lowered = (answer or "").lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def _ask_live_chat(chat_url: str, token: str, question: str, timeout: float = 30.0) -> dict[str, Any]:
    url = f"{chat_url.rstrip('/')}/api/v1/chat/ask"
    req = urllib.request.Request(
        url,
        data=json.dumps({"question": question, "document_ids": []}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


_STOPWORDS = frozenset(
    {
        "que", "con", "por", "para", "del", "las", "los", "una", "uno", "cual", "cuál",
        "como", "cómo", "donde", "dónde", "quien", "quién", "fue", "son", "esta", "está",
        "sobre", "entre", "desde", "hasta", "segun", "según", "este", "esto", "esa", "ese",
    }
)


def _local_rank_docs(corpus_dir: Path, doc_paths: list[str], query: str) -> list[str]:
    tokens = {t for t in re.findall(r"[a-z0-9áéíóúñ]{3,}", query.lower()) if t not in _STOPWORDS}
    scored: list[tuple[float, str]] = []
    for rel in doc_paths:
        path = corpus_dir / rel
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore").lower()
        score = sum(1.0 for tok in tokens if tok in content)
        if score >= 2.0:
            scored.append((score, rel))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [rel for _, rel in scored]


def run_evaluation(
    *,
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
    chat_url: str | None = None,
    token: str | None = None,
    thresholds: Thresholds = Thresholds(),
) -> dict[str, Any]:
    gt_path = corpus_dir / "ground_truth.json"
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    all_docs = [rel for paths in gt.get("sets", {}).values() for rel in paths]
    queries = gt.get("cases") or gt.get("queries") or []

    mode = "live_http" if (chat_url and token) else "local_corpus"
    query_reports: list[dict[str, Any]] = []

    rec5_list: list[float] = []
    rec10_list: list[float] = []
    prec5_list: list[float] = []
    mrr_list: list[float] = []
    ndcg5_list: list[float] = []
    cit_acc_list: list[float] = []

    for item in queries:
        q_text = str(item.get("question") or item.get("query") or "")
        expected_docs = set(
            item.get("expected_docs") or item.get("expected_documents") or item.get("relevant_docs") or []
        )
        if not expected_docs and item.get("expected_doc"):
            expected_docs = {str(item["expected_doc"])}

        if mode == "live_http":
            resp = _ask_live_chat(chat_url or "", token or "", q_text)
            sources = resp.get("sources") or []
            retrieved = [str(s.get("filename") or s.get("document_id") or "") for s in sources]
            ans_text = str(resp.get("answer") or "")
            cit_acc = citation_accuracy(ans_text, len(sources))
        else:
            retrieved = _local_rank_docs(corpus_dir, all_docs, q_text)
            cit_acc = 1.0 if retrieved else 0.0

        r5 = recall_at_k(retrieved, expected_docs, 5)
        r10 = recall_at_k(retrieved, expected_docs, 10)
        p5 = precision_at_k(retrieved, expected_docs, 5)
        mrr = reciprocal_rank(retrieved, expected_docs)
        ndcg = ndcg_at_k(retrieved, expected_docs, 5)

        rec5_list.append(r5)
        rec10_list.append(r10)
        prec5_list.append(p5)
        mrr_list.append(mrr)
        ndcg5_list.append(ndcg)
        cit_acc_list.append(cit_acc)

        query_reports.append(
            {
                "id": item.get("id", q_text[:40]),
                "question": q_text,
                "recall_at_5": round(r5, 4),
                "recall_at_10": round(r10, 4),
                "precision_at_5": round(p5, 4),
                "mrr": round(mrr, 4),
                "ndcg_at_5": round(ndcg, 4),
                "citation_accuracy": round(cit_acc, 4),
            }
        )

    refusal_hits = 0
    unanswerable_reports: list[dict[str, Any]] = []
    for probe in UNANSWERABLE_PROBES:
        if mode == "live_http":
            resp = _ask_live_chat(chat_url or "", token or "", probe["question"])
            refused = is_refusal_answer(str(resp.get("answer") or ""), str(resp.get("provider_status") or "ok"))
        else:
            retrieved = _local_rank_docs(corpus_dir, all_docs, probe["question"])
            refused = len(retrieved) == 0
        if refused:
            refusal_hits += 1
        unanswerable_reports.append({"id": probe["id"], "refused": refused})

    def _avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    metrics = {
        "recall_at_5": _avg(rec5_list),
        "recall_at_10": _avg(rec10_list),
        "precision_at_5": _avg(prec5_list),
        "mrr": _avg(mrr_list),
        "ndcg_at_5": _avg(ndcg5_list),
        "citation_accuracy": _avg(cit_acc_list),
        "unanswerable_refusal_rate": round(refusal_hits / len(UNANSWERABLE_PROBES), 4),
    }

    checks = {
        "recall_at_5_ok": metrics["recall_at_5"] >= thresholds.min_recall_at_5,
        "mrr_ok": metrics["mrr"] >= thresholds.min_mrr,
        "ndcg_at_5_ok": metrics["ndcg_at_5"] >= thresholds.min_ndcg_at_5,
        "refusal_rate_ok": metrics["unanswerable_refusal_rate"] >= thresholds.min_refusal_rate,
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "queries_evaluated": len(query_reports),
        "unanswerable_evaluated": len(unanswerable_reports),
        "metrics": metrics,
        "thresholds": {
            "min_recall_at_5": thresholds.min_recall_at_5,
            "min_mrr": thresholds.min_mrr,
            "min_ndcg_at_5": thresholds.min_ndcg_at_5,
            "min_refusal_rate": thresholds.min_refusal_rate,
        },
        "checks": checks,
        "passed": all(checks.values()),
        "queries": query_reports,
        "unanswerable": unanswerable_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Runner de evaluación RAG real (EVO-011).")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--chat-url", type=str, default=None)
    parser.add_argument("--token", type=str, default=None)
    parser.add_argument("--fail-below-thresholds", action="store_true")
    args = parser.parse_args()

    report = run_evaluation(corpus_dir=args.corpus_dir, chat_url=args.chat_url, token=args.token)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "mode": report["mode"], "metrics": report["metrics"], "passed": report["passed"]}))
    if args.fail_below_thresholds and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
