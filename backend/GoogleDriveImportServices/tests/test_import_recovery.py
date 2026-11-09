import importlib.util
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.use_cases.manage_google_drive_imports import (
    ManageGoogleDriveImports,
)
from app.config.security import DriveUser
from app.infrastructure.database.connection import Database
from app.infrastructure.database.repositories.google_drive_repository_pg import (
    GoogleDriveRepository,
)
from app.interfaces.api.v1.schemas.google_drive_schema import GoogleDriveImportRequest
from app.shared.errors import DriveConflictError

pytestmark = pytest.mark.postgres


@pytest.fixture
def imports(runtime_url, identities, engine):
    database = Database(runtime_url)
    user = DriveUser(
        str(identities["owner"]), identities["fingerprint"], identities["tenant"]
    )
    repo = GoogleDriveRepository(database, user)
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO google_drive_connections(owner_user_id,access_token_encrypted,grant_status,provider_account_id,oauth_client_id) VALUES(:u,'synthetic','ACTIVE','synthetic','synthetic')"
            ),
            {"u": user.user_id},
        )
    documents, downloads = [], []
    mode = SimpleNamespace(
        ambiguous=False, entered=None, release=None, pending=False, reject=False
    )

    def download(*args, **kwargs):
        downloads.append(args[1])
        if mode.entered:
            mode.entered.set()
            assert mode.release.wait(5)
        body = BytesIO(b"synthetic")
        return SimpleNamespace(
            content=body,
            close=body.close,
            size_bytes=9,
            filename="file.txt",
            mime_type="text/plain",
            export_mime_type=None,
            metadata=SimpleNamespace(mime_type="text/plain"),
        )

    def upload(**kwargs):
        if mode.reject:
            from app.shared.errors import UploadRejected

            raise UploadRejected("synthetic rejected authorization")
        identifier = str(uuid4())
        with engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO documents(document_id,filename,storage_path,mime_type,owner_user_id) VALUES(:d,'synthetic.txt',:p,'text/plain',:u)"
                ),
                {
                    "d": identifier,
                    "p": "synthetic-drive005-" + identifier,
                    "u": user.user_id,
                },
            )
        documents.append(identifier)
        if mode.ambiguous:
            raise httpx.ReadTimeout("synthetic ambiguous upload")
        return {
            "document_id": identifier,
            "status": "PENDING" if mode.pending else "PROCESSED",
        }

    def process(*args, **kwargs):
        raise httpx.ReadTimeout("synthetic processing timeout")

    service = ManageGoogleDriveImports(
        repo,
        SimpleNamespace(download_file=download),
        SimpleNamespace(upload=upload, process_document=process),
        None,
        SimpleNamespace(max_import_files=25),
    )
    service._valid_access_token = lambda *args: "synthetic-access"

    def payload(**changes):
        values = {
            "operation_id": str(uuid4()),
            "files": [{"file_id": "synthetic-file"}],
        }
        values.update(changes)
        return GoogleDriveImportRequest(**values)

    try:
        yield SimpleNamespace(
            service=service,
            repo=repo,
            database=database,
            user=user,
            documents=documents,
            downloads=downloads,
            mode=mode,
            payload=payload,
        )
    finally:
        database.close()
        with engine.begin() as c:
            c.execute(
                text("DELETE FROM documents WHERE document_id=ANY(:ids)"),
                {"ids": documents},
            )


def run(context, payload):
    return context.service.import_files(context.user.user_id, "synthetic", payload)


def test_operation_replay_does_not_repeat_upload_or_download(imports):
    payload = imports.payload()
    first, files = run(imports, payload)
    second, repeated = run(imports, payload)
    assert first.import_id == second.import_id and second.status == "COMPLETED"
    assert (
        len(files)
        == len(repeated)
        == len(imports.documents)
        == len(imports.downloads)
        == 1
    )
    changed = payload.model_copy(update={"metadata": {"changed": True}})
    with pytest.raises(DriveConflictError):
        run(imports, changed)
    from app.shared.errors import ImportSourceConflict

    with pytest.raises(ImportSourceConflict):
        run(imports, imports.payload())
    assert len(imports.documents) == 1


def test_ambiguous_upload_stays_reviewable_and_replay_never_duplicates(imports):
    imports.mode.ambiguous = True
    payload = imports.payload()
    result, files = run(imports, payload)
    assert result.status == files[0].status == "REVIEW_REQUIRED"
    assert files[0].document_id is None and len(imports.documents) == 1
    imports.mode.ambiguous = False
    repeated, _ = run(imports, payload)
    assert repeated.status == "REVIEW_REQUIRED" and len(imports.documents) == 1
    from app.shared.errors import ImportSourceConflict

    with pytest.raises(ImportSourceConflict):
        run(imports, imports.payload())


def test_parallel_replay_and_owner_slot_rejected_without_network_locks(imports, engine):
    imports.mode.entered, imports.mode.release = Event(), Event()
    payload = imports.payload()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run, imports, payload)
        try:
            assert imports.mode.entered.wait(5)
            with pytest.raises(DriveConflictError):
                run(imports, payload)
            with pytest.raises(DriveConflictError):
                run(imports, imports.payload())
            with engine.begin() as c:
                c.execute(text("SET LOCAL lock_timeout='1s'"))
                c.execute(
                    text("UPDATE auth_user SET password=password WHERE id=:u"),
                    {"u": int(imports.user.user_id)},
                )
                c.execute(
                    text(
                        "UPDATE google_drive_imports SET updated_at=updated_at WHERE owner_user_id=:u"
                    ),
                    {"u": imports.user.user_id},
                )
        finally:
            imports.mode.release.set()
        assert future.result()[0].status == "COMPLETED"
    assert len(imports.documents) == 1


@pytest.mark.parametrize(
    "stage,expected",
    [
        ("DOWNLOADING", "FAILED"),
        ("UPLOADING", "REVIEW_REQUIRED"),
        ("UPLOADED", "PARTIAL"),
        ("COMPLETED", "COMPLETED"),
    ],
)
def test_expired_worker_recovery_preserves_confirmed_documents_and_fences_late_results(
    imports, engine, stage, expected
):
    payload = imports.payload()
    lease, _ = imports.repo.claim_import(payload.operation_id, "a" * 64, payload, 1)
    file = imports.repo.list_import_files(lease.import_id)[0]
    imports.repo.journal_file(lease, file.import_file_id, {"status": stage})
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE google_drive_imports SET lease_until=now()-interval '1 second' WHERE import_id=:i"
            ),
            {"i": lease.import_id},
        )
    recovered = imports.repo.recover_import(lease.import_id)
    assert recovered.status == expected and recovered.lease_token is None
    with pytest.raises(DriveConflictError):
        imports.repo.journal_file(lease, file.import_file_id, {"status": "COMPLETED"})
    assert imports.documents == []


def maintenance_module():
    spec = importlib.util.spec_from_file_location(
        "maintain_imports", "/drive-checks/maintain_imports.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retention_plan_is_read_only_and_keeps_operation_tombstone_and_document(
    imports, engine
):
    payload = imports.payload()
    result, _ = run(imports, payload)
    with engine.begin() as c:
        c.execute(text("SET LOCAL session_replication_role=replica"))
        c.execute(
            text(
                "UPDATE google_drive_imports SET updated_at=now()-interval '31 days' WHERE import_id=:i"
            ),
            {"i": result.import_id},
        )
    module = maintenance_module()
    with Session(engine) as session, session.begin():
        plan = module.plan_maintenance(session)
    assert len(plan["entries"]) == 1 and "synthetic.txt" not in str(plan)
    assert len(imports.repo.list_import_files(result.import_id)) == 1
    with Session(engine) as session, session.begin():
        assert module.apply_maintenance(session, plan) == 1
    replay, files = run(imports, payload)
    assert replay.status == "PURGED" and files == [] and len(imports.documents) == 1
    from app.shared.errors import ImportSourceConflict

    with pytest.raises(ImportSourceConflict):
        run(imports, imports.payload())
    with engine.begin() as c:
        assert (
            c.scalar(
                text("SELECT count(*) FROM documents WHERE document_id=:d"),
                {"d": imports.documents[0]},
            )
            == 1
        )
    with pytest.raises(ValueError), Session(engine) as session, session.begin():
        module.apply_maintenance(session, plan)


def test_maintenance_change_after_review_rolls_back_entire_batch(imports, engine):
    ids = [
        run(imports, imports.payload(files=[{"file_id": f"synthetic-{index}"}]))[
            0
        ].import_id
        for index in range(2)
    ]
    with engine.begin() as c:
        c.execute(text("SET LOCAL session_replication_role=replica"))
        c.execute(
            text(
                "UPDATE google_drive_imports SET updated_at=now()-interval '31 days' WHERE import_id=ANY(:ids)"
            ),
            {"ids": ids},
        )
    module = maintenance_module()
    with Session(engine) as session, session.begin():
        plan = module.plan_maintenance(session)
    plan["entries"][-1]["version"] += 1
    with pytest.raises(ValueError), Session(engine) as session, session.begin():
        module.apply_maintenance(session, plan)
    assert all(
        len(imports.repo.list_import_files(identifier)) == 1 for identifier in ids
    )


def test_additive_migration_retains_legacy_data_and_marks_interruption_for_review(
    engine, identities
):
    from pathlib import Path

    with engine.connect() as c:
        transaction = c.begin()
        try:
            c.execute(
                text(
                    "ALTER TABLE google_drive_imports DROP COLUMN operation_id, DROP COLUMN request_hash, DROP COLUMN tenant_id, DROP COLUMN connection_version, DROP COLUMN version, DROP COLUMN lease_token, DROP COLUMN lease_until"
                )
            )
            identifier = c.scalar(
                text(
                    "INSERT INTO google_drive_imports(owner_user_id,status,total_files,metadata) VALUES(:u,'RUNNING',1,jsonb_build_object('synthetic',true)) RETURNING import_id"
                ),
                {"u": str(identities["owner"])},
            )
            c.execute(
                text(
                    "INSERT INTO google_drive_import_files(import_id,google_file_id,filename,mime_type,status) VALUES(:i,'synthetic','file.txt','text/plain','RUNNING')"
                ),
                {"i": identifier},
            )
            sql = Path("/drive-db/import_lifecycle.sql").read_text()
            c.execute(text(sql))
            c.execute(text(sql))
            row = c.execute(
                text(
                    "SELECT owner_user_id,status,metadata,version FROM google_drive_imports WHERE import_id=:i"
                ),
                {"i": identifier},
            ).one()
            assert row.owner_user_id == str(identities["owner"]) and row.metadata == {
                "synthetic": True
            }
            assert row.status == "REVIEW_REQUIRED" and row.version == 1
            assert (
                c.scalar(
                    text(
                        "SELECT status FROM google_drive_import_files WHERE import_id=:i"
                    ),
                    {"i": identifier},
                )
                == "REVIEW_REQUIRED"
            )
        finally:
            transaction.rollback()


def test_http_import_contract_and_body_cap(
    imports, token, runtime_url, signing_keys, monkeypatch
):
    from fastapi.testclient import TestClient
    from app.config.settings import Settings
    from app.infrastructure.google.drive_client import GoogleDriveClient
    from app.infrastructure.documents.document_upload_client import DocumentUploadClient
    from app.main import create_app

    monkeypatch.setattr(
        ManageGoogleDriveImports, "_valid_access_token", lambda *args: "synthetic"
    )
    monkeypatch.setattr(
        GoogleDriveClient,
        "download_file",
        lambda self, *args, **kwargs: imports.service._google_client.download_file(
            *args, **kwargs
        ),
    )
    monkeypatch.setattr(
        DocumentUploadClient,
        "upload",
        lambda self, **kwargs: imports.service._document_client.upload(**kwargs),
    )
    config = Settings(
        database_url=runtime_url,
        auth_jwt_public_key_path=signing_keys[1],
        google_drive_enabled=True,
        google_oauth_client_id="synthetic",
        google_oauth_client_secret="synthetic",
        google_token_encryption_key="a" * 48,
    )
    app = create_app(config)
    with TestClient(app) as client:
        path, headers = "/api/v1/google-drive/imports", token()
        assert (
            client.post(path, headers=headers, content=b"x" * 65537).status_code == 413
        )
        assert imports.documents == []
        assert (
            client.post(
                path, headers=headers, json={"files": [{"file_id": "synthetic"}]}
            ).status_code
            == 422
        )
        payload = imports.payload().model_dump()
        first = client.post(path, headers=headers, json=payload)
        assert first.status_code == 200 and first.json()["status"] == "COMPLETED"
        second = client.post(path, headers=headers, json=payload)
        assert (
            second.json()["import_id"] == first.json()["import_id"]
            and len(imports.documents) == 1
        )


def test_global_capacity_two_owners_and_no_premature_completion(imports, identities):
    other = GoogleDriveRepository(
        imports.database,
        DriveUser(
            str(identities["other"]), identities["fingerprint"], identities["tenant"]
        ),
    )
    one, _ = imports.repo.claim_import(str(uuid4()), "a" * 64, imports.payload(), 1)
    two, _ = other.claim_import(str(uuid4()), "b" * 64, imports.payload(), 1)
    assert one.owner_user_id != two.owner_user_id
    with pytest.raises(DriveConflictError):
        imports.repo.claim_import(str(uuid4()), "c" * 64, imports.payload(), 1)
    with pytest.raises(DriveConflictError):
        imports.repo.complete_operation(one)


def test_permission_revocation_before_upload_closes_spool_and_never_creates_document(
    imports, engine, identities
):
    from fastapi import HTTPException

    original = imports.service._google_client.download_file
    bodies = []

    def revoked(*args, **kwargs):
        downloaded = original(*args, **kwargs)
        bodies.append(downloaded.content)
        with engine.begin() as c:
            c.execute(
                text("DELETE FROM tenant_group_permissions WHERE group_id=:g"),
                {"g": identities["group"]},
            )
        return downloaded

    imports.service._google_client.download_file = revoked
    with pytest.raises(HTTPException) as error:
        run(imports, imports.payload())
    assert error.value.status_code == 403
    assert imports.documents == [] and all(body.closed for body in bodies)


def test_processing_timeout_retains_known_document_and_never_reuploads(imports):
    imports.mode.pending = True
    payload = imports.payload()
    result, files = run(imports, payload)
    assert result.status == "PARTIAL" and result.processed_files == 1
    assert (
        files[0].document_id == imports.documents[0] and files[0].status == "COMPLETED"
    )
    assert files[0].metadata_["document_status"] == "REVIEW_REQUIRED"
    run(imports, payload)
    assert len(imports.documents) == 1


def test_known_authorization_rejection_does_not_create_or_repeat_documents(imports):
    imports.mode.reject = True
    payload = imports.payload(
        files=[{"file_id": "synthetic-one"}, {"file_id": "synthetic-two"}]
    )
    result, files = run(imports, payload)
    assert result.status == "FAILED" and result.failed_files == 2
    assert imports.documents == [] and len(imports.downloads) == 1
    imports.mode.reject = False
    next_attempt = payload.model_copy(update={"operation_id": str(uuid4())})
    result, _ = run(imports, next_attempt)
    assert result.status == "COMPLETED" and len(imports.documents) == 2
