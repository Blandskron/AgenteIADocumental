"""Explicit offline inventory/apply; sources are opened read-only and never deleted."""
import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def main():
    sys.path.insert(0, "/app")
    from app.config.export_limits import GLOBAL_BYTES, MAX_PAGES, RETENTION_DAYS
    from app.infrastructure.pdf.legacy import read_legacy

    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        raise ValueError("Limit must be 1..100.")
    url = os.environ["EXPORT_MIGRATION_DATABASE_URL"]
    engine = create_engine(url, hide_parameters=True)
    manifest_path = Path(args.manifest)
    try:
        with Session(engine) as session:
            if args.apply and manifest_path.stat().st_size > 131072:
                raise ValueError("Approved manifest exceeds limit.")
            approved = json.loads(manifest_path.read_text()) if args.apply else None
            if approved is not None and (type(approved) is not list or not 0 < len(approved) <= 100):
                raise ValueError("Invalid approved manifest.")
            if args.apply:
                session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('blandskron.export.capacity',0))"))
            query = """
                SELECT e.export_id,e.owner_user_id,e.storage_path,e.file_size_bytes,e.pdf_sha256,
                       EXISTS (SELECT 1 FROM auth_user u WHERE u.id::text=e.owner_user_id) AS known_owner
                FROM document_exports e
            """
            if args.apply:
                rows = session.execute(text(query + " WHERE e.export_id=ANY(:ids) ORDER BY e.export_id FOR UPDATE"),
                                       {"ids": [entry["export_id"] for entry in approved]}).all()
            else:
                rows = session.execute(text(query + " WHERE e.pdf_data IS NULL ORDER BY e.export_id LIMIT :limit FOR UPDATE"),
                                       {"limit": args.limit}).all()
            inventory = []
            by_id = {entry["export_id"]: entry for entry in approved} if approved else {}
            for row in rows:
                if args.apply and row.export_id not in by_id:
                    continue
                entry = {"export_id": row.export_id, "owner_user_id": row.owner_user_id}
                try:
                    if args.apply and row.pdf_sha256 is not None:
                        entry.update(sha256=row.pdf_sha256, byte_count=row.file_size_bytes, state="ready")
                        if entry != by_id[row.export_id]:
                            raise ValueError("Previously migrated record differs")
                        inventory.append(entry)
                        continue
                    if not row.known_owner:
                        raise ValueError("Unresolved owner")
                    content, digest = read_legacy(args.base, row.storage_path)
                    reader = PdfReader(BytesIO(content), strict=True)
                    if reader.is_encrypted or not 0 < len(reader.pages) <= MAX_PAGES or len(content) != row.file_size_bytes:
                        raise ValueError("Legacy PDF needs manual review")
                    root = reader.trailer["/Root"]
                    if (any(key in root for key in ["/OpenAction", "/AA", "/Names", "/AcroForm", "/Collection"])
                            or any(page.get("/Annots") or page.get("/AA") for page in reader.pages)):
                        raise ValueError("Active or interactive legacy PDF needs manual review")
                    entry.update(sha256=digest, byte_count=len(content), state="ready")
                    if args.apply:
                        if entry != by_id[row.export_id]:
                            raise ValueError("Approved inventory changed")
                        total = session.scalar(text("SELECT coalesce(sum(octet_length(pdf_data)),0) FROM document_exports"))
                        if total + len(content) > GLOBAL_BYTES:
                            raise ValueError("Database capacity exceeded")
                        session.execute(text("""
                            UPDATE document_exports SET pdf_data=:data,pdf_sha256=:digest,expires_at=:expiry
                            WHERE export_id=:id AND pdf_data IS NULL
                        """), {"id": row.export_id, "data": content, "digest": digest,
                               "expiry": datetime.now(UTC) + timedelta(days=RETENTION_DAYS)})
                except Exception:
                    if args.apply:
                        raise RuntimeError("Migration stopped; transaction rolled back. Re-inventory and review.") from None
                    entry = {"export_id": row.export_id, "owner_user_id": row.owner_user_id, "state": "review_required"}
                inventory.append(entry)
            if args.apply:
                if len(inventory) != len(approved):
                    raise RuntimeError("Approved rows changed or are outside this batch; transaction rolled back.")
                session.commit()
            else:
                with os.fdopen(os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as output:
                    json.dump(inventory, output, indent=2)
                session.rollback()
            print("Legacy inventory/apply completed; sources preserved. Rows:", len(inventory))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
