"""Offline reviewed recovery/retention. Never uploads, deletes documents, or removes operation tombstones."""

import argparse
import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import (
    GoogleDriveImportFileModel as File,
    GoogleDriveImportModel as Import,
)
from app.infrastructure.database.repositories.import_repository import ImportRepository


def snapshot(session, row, lock=False):
    query = (
        select(File)
        .where(File.import_id == row.import_id)
        .order_by(File.import_file_id)
    )
    files = list(session.scalars(query.with_for_update() if lock else query))
    values = {
        "import": {
            column.name: getattr(
                row, column.key if column.name != "metadata" else "metadata_"
            )
            for column in Import.__table__.columns
        },
        "files": [
            {
                column.name: getattr(
                    file, column.key if column.name != "metadata" else "metadata_"
                )
                for column in File.__table__.columns
            }
            for file in files
        ],
    }
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, default=str).encode()
    ).hexdigest(), files


def plan_maintenance(session):
    now = session.scalar(select(func.clock_timestamp()))
    rows = session.scalars(
        select(Import)
        .where(
            (Import.lease_until <= now)
            | (
                (Import.updated_at < now - timedelta(days=30))
                & Import.status.in_(["COMPLETED", "PARTIAL", "FAILED"])
            )
        )
        .order_by(Import.import_id)
        .limit(1000)
    )
    entries = []
    for row in rows:
        fingerprint, files = snapshot(session, row)
        if row.lease_token and row.lease_until <= now:
            action = "recover"
        elif not row.lease_token and all(
            file.status == "FAILED"
            or (file.status == "COMPLETED" and not file.error_message)
            for file in files
        ):
            action = "purge_history"
        else:
            continue
        entries.append(
            {
                "import_id": row.import_id,
                "version": row.version,
                "action": action,
                "fingerprint": fingerprint,
            }
        )
    return {"format": 1, "entries": entries}


def apply_maintenance(session, plan):
    if (
        plan.get("format") != 1
        or not isinstance(plan.get("entries"), list)
        or len(plan["entries"]) > 1000
    ):
        raise ValueError("Invalid maintenance plan.")
    for entry in sorted(plan["entries"], key=lambda value: value["import_id"]):
        row = session.scalar(
            select(Import)
            .where(Import.import_id == entry["import_id"])
            .with_for_update()
        )
        if (
            row is None
            or row.version != entry["version"]
            or snapshot(session, row, lock=True)[0] != entry["fingerprint"]
        ):
            raise ValueError(
                "Import changed after review; regenerate the complete plan."
            )
        now = session.scalar(select(func.clock_timestamp()))
        if entry["action"] == "recover" and row.lease_token and row.lease_until <= now:
            ImportRepository()._recover_locked(session, row)
        elif (
            entry["action"] == "purge_history"
            and not row.lease_token
            and row.updated_at < now - timedelta(days=30)
            and row.status in {"COMPLETED", "PARTIAL", "FAILED"}
            and all(
                file.status == "FAILED"
                or (file.status == "COMPLETED" and not file.error_message)
                for file in snapshot(session, row)[1]
            )
        ):
            for file in snapshot(session, row)[1]:
                file.filename, file.mime_type, file.size_bytes = (
                    "Retained operation",
                    "application/octet-stream",
                    None,
                )
                file.metadata_, file.error_message = {}, None
            row.status, row.metadata_, row.error_message = "PURGED", {}, None
            row.version += 1
        else:
            raise ValueError("Maintenance action is no longer applicable.")
        session.flush()
    return len(plan["entries"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--plan", type=Path)
    choice.add_argument("--apply", type=Path)
    args = parser.parse_args()
    url = os.environ.get("DRIVE_MAINTENANCE_DATABASE_URL")
    if not url or not url.startswith("postgresql+psycopg://"):
        raise SystemExit("Explicit maintenance database configuration is required.")
    engine = create_engine(url, hide_parameters=True)
    try:
        with Session(engine) as session, session.begin():
            from sqlalchemy import text

            session.execute(text("SET LOCAL lock_timeout='5s'"))
            session.execute(text("SET LOCAL statement_timeout='30s'"))
            if args.plan:
                with args.plan.open("x", encoding="utf-8") as output:
                    json.dump(plan_maintenance(session), output, indent=2)
                print(
                    "Plan created; no imports were changed. Review outside Git before applying."
                )
            else:
                count = apply_maintenance(
                    session, json.loads(args.apply.read_text(encoding="utf-8"))
                )
                print(
                    f"Applied {count} reviewed actions; documents and operation tombstones retained."
                )
    except Exception:
        raise SystemExit(
            "Maintenance stopped; all SQL changes rolled back. Regenerate the plan."
        ) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
