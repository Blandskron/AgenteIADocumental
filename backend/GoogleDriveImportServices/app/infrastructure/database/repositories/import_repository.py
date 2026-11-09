import secrets
from datetime import timedelta

from sqlalchemy import func, select, text

from app.infrastructure.database.models import (
    GoogleDriveImportFileModel as File,
    GoogleDriveImportModel as Import,
)
from app.shared.errors import DriveConflictError, ImportSourceConflict


class ImportRepository:
    def replay_import(self, operation_id, request_hash):
        with self._session() as session:
            row = session.scalar(
                select(Import)
                .where(
                    Import.owner_user_id == self._user.user_id,
                    Import.operation_id == operation_id,
                )
                .with_for_update()
            )
            if row is None:
                return None
            if (
                row.request_hash != request_hash
                or row.tenant_id != self._user.tenant_id
            ):
                raise DriveConflictError(
                    "Operation key belongs to another request or tenant."
                )
            self._recover_locked(session, row)
            if row.lease_token:
                raise DriveConflictError("Import is already running.")
            session.commit()
            return row

    def _recover_locked(self, session, record):
        now = session.scalar(select(func.clock_timestamp()))
        if record.lease_token and record.lease_until <= now:
            files = list(
                session.scalars(
                    select(File)
                    .where(File.import_id == record.import_id)
                    .with_for_update()
                )
            )
            for file in files:
                if file.status == "UPLOADING":
                    file.status = "REVIEW_REQUIRED"
                    file.error_message = (
                        "Upload outcome is unknown; do not repeat automatically."
                    )
                elif file.status in {"PENDING", "DOWNLOADING", "RUNNING"}:
                    file.status = "FAILED"
                    file.error_message = "Import was interrupted before upload."
            record.processed_files = sum(
                file.status in {"COMPLETED", "UPLOADED"} for file in files
            )
            record.failed_files = sum(file.status == "FAILED" for file in files)
            record.status = (
                "REVIEW_REQUIRED"
                if any(file.status == "REVIEW_REQUIRED" for file in files)
                else "COMPLETED"
                if files
                and all(
                    file.status == "COMPLETED" and not file.error_message
                    for file in files
                )
                else "PARTIAL"
                if record.processed_files
                else "FAILED"
            )
            record.error_message = (
                "Interrupted import recovered; review the per-file outcomes."
                if record.status != "COMPLETED"
                else None
            )
            record.lease_token = record.lease_until = None
            record.version += 1
        return record

    def claim_import(self, operation_id, request_hash, payload, connection_version):
        with self._session() as session:
            session.execute(
                text(
                    "SELECT pg_advisory_xact_lock(hashtextextended('blandskron.drive.import-slots',0))"
                )
            )
            existing = session.scalar(
                select(Import)
                .where(
                    Import.owner_user_id == self._user.user_id,
                    Import.operation_id == operation_id,
                )
                .with_for_update()
            )
            if existing:
                if (
                    existing.request_hash != request_hash
                    or existing.tenant_id != self._user.tenant_id
                ):
                    raise DriveConflictError(
                        "Operation key belongs to another request or tenant."
                    )
                self._recover_locked(session, existing)
                if existing.lease_token:
                    raise DriveConflictError("Import is already running.")
                session.commit()
                return existing, False
            now = session.scalar(select(func.clock_timestamp()))
            active = list(
                session.scalars(select(Import).where(Import.lease_until > now).limit(3))
            )
            if len(active) >= 2 or any(
                row.owner_user_id == self._user.user_id for row in active
            ):
                raise DriveConflictError("Import capacity is busy.")
            prior = session.scalar(
                select(File.import_file_id)
                .join(Import, File.import_id == Import.import_id)
                .where(
                    Import.owner_user_id == self._user.user_id,
                    File.google_file_id.in_([item.file_id for item in payload.files]),
                    File.status.in_(
                        ["UPLOADING", "UPLOADED", "COMPLETED", "REVIEW_REQUIRED"]
                    ),
                )
                .limit(1)
            )
            if prior:
                raise ImportSourceConflict(
                    "A selected file was already uploaded or needs review."
                )
            record = Import(
                owner_user_id=self._user.user_id,
                operation_id=operation_id,
                request_hash=request_hash,
                tenant_id=self._user.tenant_id,
                connection_version=connection_version,
                status="RUNNING",
                total_files=len(payload.files),
                processed_files=0,
                failed_files=0,
                metadata_={
                    **payload.metadata,
                    "source": "google_drive",
                    "folder_id": payload.folder_id,
                },
                lease_token=secrets.token_urlsafe(32),
                lease_until=now + timedelta(minutes=15),
            )
            session.add(record)
            session.flush()
            for item in payload.files:
                session.add(
                    File(
                        import_id=record.import_id,
                        google_file_id=item.file_id,
                        filename=item.name or item.file_id,
                        mime_type=item.mime_type or "application/octet-stream",
                        export_mime_type=item.export_mime_type,
                        status="PENDING",
                        metadata_={},
                    )
                )
            session.commit()
            return record, True

    def _operation(self, session, lease):
        record = session.scalar(
            select(Import)
            .where(
                Import.import_id == lease.import_id,
                Import.owner_user_id == self._user.user_id,
            )
            .with_for_update()
        )
        now = session.scalar(select(func.clock_timestamp()))
        if (
            record is None
            or not record.lease_token
            or record.lease_token != lease.lease_token
            or record.version != lease.version
            or record.lease_until <= now
        ):
            raise DriveConflictError("Import operation is no longer current.")
        return record

    def guard_import(self, lease):
        with self._session() as session:
            self._operation(session, lease)

    def journal_file(self, lease, file_id, values):
        with self._session() as session:
            self._operation(session, lease)
            row = session.scalar(
                select(File)
                .where(
                    File.import_id == lease.import_id, File.import_file_id == file_id
                )
                .with_for_update()
            )
            if row is None:
                raise DriveConflictError("Import file is no longer available.")
            for name, value in values.items():
                setattr(row, name, value)
            session.commit()

    def complete_operation(self, lease):
        with self._session() as session:
            record = self._operation(session, lease)
            files = list(
                session.scalars(select(File).where(File.import_id == record.import_id))
            )
            if any(
                file.status
                not in {"COMPLETED", "UPLOADED", "FAILED", "REVIEW_REQUIRED"}
                for file in files
            ):
                raise DriveConflictError("Import files are not in a terminal state.")
            record.processed_files = sum(
                file.status in {"UPLOADED", "COMPLETED"} for file in files
            )
            record.failed_files = sum(file.status == "FAILED" for file in files)
            unknown = any(file.status == "REVIEW_REQUIRED" for file in files)
            warnings = any(
                file.status == "UPLOADED" or file.error_message for file in files
            )
            record.status = (
                "REVIEW_REQUIRED"
                if unknown
                else "COMPLETED"
                if not warnings
                else "PARTIAL"
                if record.processed_files
                else "FAILED"
            )
            record.error_message = (
                "Review import file outcomes before retrying."
                if record.status != "COMPLETED"
                else None
            )
            record.lease_token = record.lease_until = None
            record.version += 1
            session.commit()
            return record

    def recover_import(self, import_id):
        with self._session() as session:
            record = self._owned_import(session, import_id)
            session.refresh(record, with_for_update=True)
            self._recover_locked(session, record)
            session.commit()
            return record
