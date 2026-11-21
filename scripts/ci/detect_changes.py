#!/usr/bin/env python3
"""Determine affected CI scopes from git diff for selective fast validation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_SERVICES = [
    {
        "name": "conversation",
        "dir": "backend/ConversationServices",
        "test_service": "conversation-tests",
        "audit_service": "",
        "role_service": "conversation-db-role",
        "app_service": "conversation-service",
        "needs_auth": False,
        "extra_ruff_paths": "",
    },
    {
        "name": "rag-chat",
        "dir": "backend/RagDocumentChatServices",
        "test_service": "rag-chat-tests",
        "audit_service": "",
        "role_service": "rag-chat-db-role",
        "app_service": "rag-document-chat-service",
        "needs_auth": False,
        "extra_ruff_paths": "",
    },
    {
        "name": "embedding",
        "dir": "backend/RagDocumentEmbeddingServices",
        "test_service": "embedding-tests",
        "audit_service": "",
        "role_service": "embedding-db-role",
        "app_service": "rag-document-embedding-service",
        "needs_auth": False,
        "extra_ruff_paths": "",
    },
    {
        "name": "search",
        "dir": "backend/DocumentSearchServices",
        "test_service": "search-tests",
        "audit_service": "",
        "role_service": "search-db-role",
        "app_service": "document-search-service",
        "needs_auth": False,
        "extra_ruff_paths": "",
    },
    {
        "name": "access",
        "dir": "backend/DocumentAccessServices",
        "test_service": "access-tests",
        "audit_service": "access-audit",
        "role_service": "access-db-role",
        "app_service": "document-access-service",
        "needs_auth": True,
        "extra_ruff_paths": "",
    },
    {
        "name": "library",
        "dir": "backend/DocumentLibraryServices",
        "test_service": "library-tests",
        "audit_service": "library-audit",
        "role_service": "library-db-role",
        "app_service": "document-library-service",
        "needs_auth": False,
        "extra_ruff_paths": "",
    },
    {
        "name": "transfer",
        "dir": "backend/DocumentTransferServices",
        "test_service": "transfer-tests",
        "audit_service": "transfer-audit",
        "role_service": "transfer-db-role",
        "app_service": "document-transfer-service",
        "needs_auth": False,
        "extra_ruff_paths": "",
    },
    {
        "name": "profile",
        "dir": "backend/ProfileServices",
        "test_service": "profile-tests",
        "audit_service": "profile-audit",
        "role_service": "profile-db-role",
        "app_service": "profile-service",
        "needs_auth": True,
        "extra_ruff_paths": "/profile-checks",
    },
    {
        "name": "export",
        "dir": "backend/DocumentExportServices",
        "test_service": "export-tests",
        "audit_service": "export-audit",
        "role_service": "export-db-role",
        "app_service": "document-export-service",
        "needs_auth": True,
        "extra_ruff_paths": "/export-checks",
    },
    {
        "name": "drive",
        "dir": "backend/GoogleDriveImportServices",
        "test_service": "drive-tests",
        "audit_service": "drive-audit",
        "role_service": "drive-db-role",
        "app_service": "google-drive-import-service",
        "needs_auth": True,
        "extra_ruff_paths": "/drive-checks",
    },
]

SERVICE_SCRIPT_PREFIXES = {
    "profile": ("scripts/profile/", "scripts/database/profile/"),
    "export": ("scripts/export/", "scripts/database/export/"),
    "drive": ("scripts/drive/", "scripts/database/drive/"),
    "conversation": ("scripts/database/conversation/",),
    "rag-chat": ("scripts/database/rag-chat/",),
    "embedding": ("scripts/database/embedding/",),
    "search": ("scripts/database/search/",),
    "access": ("scripts/database/access/",),
    "library": ("scripts/database/library/",),
    "transfer": ("scripts/database/transfer/",),
}

GLOBAL_INFRA_PREFIXES = (
    ".github/workflows/",
    "docker/docker-compose.yml",
    "docker/compose/",
    ".env.example",
    "scripts/ci/",
    "scripts/release/prepare_verification.mjs",
)


def changed_files(base: str | None, head: str) -> list[str]:
    if not base or set(base) == {"0"}:
        return []
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        proc = subprocess.run(
            ["git", "diff", "--name-only", base, head],
            capture_output=True,
            text=True,
            check=False,
        )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def compute_scopes(files: list[str], force_all: bool) -> dict[str, object]:
    if force_all or not files:
        return {
            "docs": True,
            "compose": True,
            "auth": True,
            "frontend": True,
            "postgres": True,
            "rag_groq": True,
            "studio_eval": True,
            "database": True,
            "services": [],
        }

    def any_starts(*prefixes: str) -> bool:
        return any(f.startswith(prefixes) for f in files)

    def any_is_md() -> bool:
        return any(f.endswith(".md") for f in files)

    global_infra = any_starts(*GLOBAL_INFRA_PREFIXES)
    sql_or_pg = any_starts("scripts/database/", "docker/postgres/")
    compose = global_infra or any_starts("docker/", "backend/AuthServices/Dockerfile")
    database = sql_or_pg
    auth = global_infra or sql_or_pg or any_starts("backend/AuthServices/")
    frontend = global_infra or any_starts("frontend/")
    postgres = sql_or_pg or any_starts("scripts/release/verify_postgres_upgrade.mjs")
    rag_groq = global_infra or any_starts("backend/RagDocumentChatServices/")
    studio_eval = global_infra or any_starts(
        "backend/KnowledgeStudioServices/",
        "scripts/eval/",
        "tests/fixtures/eval_corpus/",
    )
    docs = any_is_md() or any_starts("docs/", "scripts/ci/check_docs_links.py")

    selected_services = []
    for svc in BACKEND_SERVICES:
        prefixes = (f"{svc['dir']}/",) + SERVICE_SCRIPT_PREFIXES.get(svc["name"], ())
        if any_starts(*prefixes):
            selected_services.append(svc)
    if sql_or_pg and not selected_services:
        selected_services = [
            svc for svc in BACKEND_SERVICES if svc["name"] in ("conversation", "search", "access", "library")
        ]

    return {
        "docs": docs,
        "compose": compose,
        "auth": auth,
        "frontend": frontend,
        "postgres": postgres,
        "rag_groq": rag_groq,
        "studio_eval": studio_eval,
        "database": database,
        "services": selected_services,
    }


def write_outputs(scopes: dict[str, object], github_output: str | None) -> None:
    lines = [
        f"docs={'true' if scopes['docs'] else 'false'}",
        f"compose={'true' if scopes['compose'] else 'false'}",
        f"auth={'true' if scopes['auth'] else 'false'}",
        f"frontend={'true' if scopes['frontend'] else 'false'}",
        f"postgres={'true' if scopes['postgres'] else 'false'}",
        f"rag_groq={'true' if scopes['rag_groq'] else 'false'}",
        f"studio_eval={'true' if scopes['studio_eval'] else 'false'}",
        f"database={'true' if scopes['database'] else 'false'}",
        f"has_services={'true' if scopes['services'] else 'false'}",
        f"services={json.dumps(scopes['services'], separators=(',', ':'))}",
    ]
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    else:
        print("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.environ.get("BASE_REF", ""))
    parser.add_argument("--head", default=os.environ.get("HEAD_REF", "HEAD"))
    parser.add_argument("--force-all", action="store_true")
    args = parser.parse_args()

    files = [] if args.force_all else changed_files(args.base, args.head)
    scopes = compute_scopes(files, force_all=args.force_all)
    print(f"Changed files ({len(files)}): {files[:20]}", file=sys.stderr)
    write_outputs(scopes, os.environ.get("GITHUB_OUTPUT"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

