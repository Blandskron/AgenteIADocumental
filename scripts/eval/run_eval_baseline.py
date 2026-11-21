#!/usr/bin/env python3
"""Harness reproducible de evaluación sobre el corpus sintético S1-S5 (R0-04).

Valida la integridad del corpus sintético, ejecuta pruebas defensivas de archivo
(path traversal, zip-bomb en memoria, caracteres RTL, patrones XSS/inyección) y
mide la línea base de recuperación léxica/chunking emitiendo un reporte JSON en
`.release-reports/EVAL_BASELINE.json`.

No requiere credenciales, servicios externos ni datos reales.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "eval_corpus"
DEFAULT_OUTPUT = REPO_ROOT / ".release-reports" / "EVAL_BASELINE.json"

MAX_ZIP_EXPANDED_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_ZIP_RATIO = 50.0
FIXED_CHUNK_SIZE = 900
FIXED_CHUNK_OVERLAP = 150

SECRET_PATTERNS = (
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"BEGIN (?:RSA |EC )?PRIVATE KEY"),
)

XSS_MARKERS = ("<script", "foreignobject", "onerror=", "onload=")
INJECTION_MARKERS = (
    "ignora todas las instrucciones",
    "ignora la pregunta del usuario",
    "volca el sistema",
    "pwned_by_doc",
)
RTL_CONTROL_CHARS = ("\u202e", "\u202d", "\u202a", "\u202b", "\u202c", "\u2066", "\u2067", "\u2068", "\u2069")


@dataclass(frozen=True)
class Chunk:
    doc_path: str
    chunk_index: int
    content: str


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    return decomposed.encode("ascii", "ignore").decode("ascii")


def tokenize(value: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9][a-z0-9_-]{1,}", normalize_text(value)) if len(tok) >= 2}


def fixed_window_chunks(doc_path: str, text: str, size: int = FIXED_CHUNK_SIZE, overlap: int = FIXED_CHUNK_OVERLAP) -> list[Chunk]:
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    step = max(1, size - overlap)
    while start < len(text):
        piece = text[start : start + size]
        if piece.strip():
            chunks.append(Chunk(doc_path=doc_path, chunk_index=idx, content=piece))
            idx += 1
        if start + size >= len(text):
            break
        start += step
    return chunks


def build_synthetic_zip_bomb_bytes() -> bytes:
    """Genera en memoria un ZIP sintético con ratio > 100x para validar guardas anti zip-bomb."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("synthetic_bomb.txt", b"0" * (2 * 1024 * 1024))
    return buf.getvalue()


def inspect_zip_safety(raw: bytes, max_expanded: int = MAX_ZIP_EXPANDED_BYTES, max_ratio: float = MAX_ZIP_RATIO) -> dict[str, Any]:
    reasons: list[str] = []
    total_uncompressed = 0
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if name.startswith("/") or ".." in Path(name).parts:
                reasons.append(f"path_traversal:{name}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                reasons.append(f"symlink:{name}")
            total_uncompressed += info.file_size
            compressed = max(1, info.compress_size)
            ratio = info.file_size / compressed
            if ratio > max_ratio:
                reasons.append(f"zip_bomb_ratio:{ratio:.1f}>{max_ratio:.1f}")
    if total_uncompressed > max_expanded:
        reasons.append(f"zip_bomb_size:{total_uncompressed}>{max_expanded}")
    return {"safe": not reasons, "reasons": reasons, "uncompressed_bytes": total_uncompressed}


def evaluate_corpus(corpus_dir: Path) -> dict[str, Any]:
    gt_path = corpus_dir / "ground_truth.json"
    gt = json.loads(gt_path.read_text(encoding="utf-8"))

    documents: dict[str, str] = {}
    doc_hashes: dict[str, str] = {}
    all_chunks: list[Chunk] = []
    secret_hits: list[str] = []

    for set_name, rel_paths in gt["sets"].items():
        for rel in rel_paths:
            full_path = corpus_dir / rel
            if not full_path.is_file():
                raise FileNotFoundError(f"Fixture faltante en {set_name}: {rel}")
            raw_bytes = full_path.read_bytes()
            text = raw_bytes.decode("utf-8")
            documents[rel] = text
            doc_hashes[rel] = hashlib.sha256(raw_bytes).hexdigest()
            all_chunks.extend(fixed_window_chunks(rel, text))
            for pat in SECRET_PATTERNS:
                if pat.search(text):
                    secret_hits.append(f"{rel}:{pat.pattern}")

    # Baseline retrieval: token overlap (proxy FTS/léxico) vs substring exacto (proxy ILIKE actual)
    case_results: list[dict[str, Any]] = []
    token_recall_sum = 0.0
    ilike_recall_sum = 0.0
    term_coverage_sum = 0.0
    cases_with_terms = 0

    for case in gt["cases"]:
        query = case["query"]
        q_norm = normalize_text(query)
        q_tokens = tokenize(query)
        expected_docs = set(case["expected_docs"])

        # Proxy ILIKE actual (DocumentSearchServices usa ILIKE '%query%' completo)
        ilike_hits = {
            chunk.doc_path
            for chunk in all_chunks
            if q_norm in normalize_text(chunk.content)
        }
        ilike_recall = len(expected_docs & ilike_hits) / len(expected_docs) if expected_docs else 1.0
        ilike_recall_sum += ilike_recall

        # Proxy token overlap Top-5 (línea base léxica sin embeddings ni HNSW)
        scored: list[tuple[float, str, str]] = []
        for chunk in all_chunks:
            c_tokens = tokenize(chunk.content)
            overlap = len(q_tokens & c_tokens)
            if overlap > 0:
                score = overlap / max(1, len(q_tokens))
                scored.append((score, chunk.doc_path, chunk.content))
        scored.sort(key=lambda item: item[0], reverse=True)
        top_k = scored[:5]
        top_docs = {doc for _, doc, _ in top_k}
        token_recall = len(expected_docs & top_docs) / len(expected_docs) if expected_docs else 1.0
        token_recall_sum += token_recall

        expected_terms = case.get("expected_terms", [])
        top_text = normalize_text(" ".join(content for _, _, content in top_k))
        if expected_terms:
            found_terms = [t for t in expected_terms if normalize_text(t) in top_text]
            term_cov = len(found_terms) / len(expected_terms)
            term_coverage_sum += term_cov
            cases_with_terms += 1
        else:
            term_cov = None

        case_results.append({
            "id": case["id"],
            "set": case["set"],
            "type": case["type"],
            "expected_docs": sorted(expected_docs),
            "ilike_recall": round(ilike_recall, 4),
            "lexical_top5_recall": round(token_recall, 4),
            "expected_terms_in_top5": round(term_cov, 4) if term_cov is not None else None,
        })

    # Controles adversariales S4 (presencia verificada en corpus + guardas sintéticas)
    s4_text = "\n".join(documents[p] for p in gt["sets"]["S4-adversarial"])
    s4_norm = normalize_text(s4_text)
    zip_bomb_check = inspect_zip_safety(build_synthetic_zip_bomb_bytes())
    traversal_buf = io.BytesIO()
    with zipfile.ZipFile(traversal_buf, "w") as zf:
        zf.writestr("../../etc/passwd", b"synthetic")
    traversal_check = inspect_zip_safety(traversal_buf.getvalue())

    adversarial_checks = {
        "prompt_injection_fixture_present": any(m in s4_norm for m in INJECTION_MARKERS),
        "xss_svg_fixture_present": all(m in s4_text.lower() for m in XSS_MARKERS),
        "rtl_unicode_fixture_present": any(ch in s4_text for ch in RTL_CONTROL_CHARS),
        "path_traversal_zip_rejected": not traversal_check["safe"],
        "zip_bomb_rejected": not zip_bomb_check["safe"],
        "zero_real_secrets_in_corpus": len(secret_hits) == 0,
    }

    total_cases = len(gt["cases"])
    return {
        "schema_version": "1.0.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "corpus_version": gt["version"],
        "synthetic_only": bool(gt.get("synthetic_only", False)),
        "document_count": len(documents),
        "fixed_chunk_count": len(all_chunks),
        "sets": {k: len(v) for k, v in gt["sets"].items()},
        "document_sha256": doc_hashes,
        "baseline_metrics": {
            "total_cases": total_cases,
            "ilike_avg_doc_recall": round(ilike_recall_sum / total_cases, 4) if total_cases else 0.0,
            "lexical_top5_avg_doc_recall": round(token_recall_sum / total_cases, 4) if total_cases else 0.0,
            "lexical_top5_avg_term_coverage": round(term_coverage_sum / cases_with_terms, 4) if cases_with_terms else 0.0,
        },
        "adversarial_checks": adversarial_checks,
        "all_adversarial_checks_passed": all(adversarial_checks.values()),
        "cases": case_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta el harness reproducible sobre el corpus sintético S1-S5.")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = evaluate_corpus(args.corpus_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    metrics = report["baseline_metrics"]
    print(
        f"Eval baseline OK ({report['document_count']} docs, {report['fixed_chunk_count']} chunks): "
        f"ilike_recall={metrics['ilike_avg_doc_recall']}, "
        f"lexical_top5_recall={metrics['lexical_top5_avg_doc_recall']}, "
        f"term_coverage={metrics['lexical_top5_avg_term_coverage']}, "
        f"adversarial_ok={report['all_adversarial_checks_passed']} -> {args.output}"
    )
    return 0 if report["all_adversarial_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
