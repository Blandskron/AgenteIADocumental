import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.application.use_cases.manage_google_drive_imports import ManageGoogleDriveImports
from app.config.security import DriveUser
from app.infrastructure.database.connection import Database
from app.infrastructure.database.repositories.google_drive_repository_pg import GoogleDriveRepository
from app.interfaces.api.v1.schemas.google_drive_schema import GoogleDriveFileRequest, GoogleDriveImportRequest
from app.shared.errors import NotFoundError


@pytest.fixture
def committed_records(monkeypatch):
    # This historical suite isolates the folder protocol; identity is covered separately.
    monkeypatch.setattr('app.infrastructure.database.repositories.google_drive_repository_pg.check_identity', lambda *args: None)
    database = Database(os.environ['DRIVE_TEST_DATABASE_URL'])
    folder_id, foreign_id, document_id = uuid4().hex, uuid4().hex, uuid4().hex
    try:
        with database.session() as session:
            session.execute(text("INSERT INTO document_folders (folder_id,name,owner_user_id) VALUES (:id,:id,:owner)"), [
                {"id": folder_id, "owner": "42"}, {"id": foreign_id, "owner": "43"},
            ])
            session.execute(text("""INSERT INTO documents (document_id,filename,storage_path,mime_type,owner_user_id)
                VALUES (:id,'synthetic.txt','lib004-drive-synthetic.txt','text/plain','42')"""), {"id": document_id})
            session.commit()
        yield database, folder_id, foreign_id, document_id
    finally:
        with database.session() as session:
            session.execute(text("DELETE FROM documents WHERE document_id=:id"), {"id": document_id})
            session.execute(text("DELETE FROM document_folders WHERE folder_id IN (:own,:foreign)"), {"own": folder_id, "foreign": foreign_id})
            session.commit()
        database.close()


@pytest.mark.postgres
def test_repository_checks_owner_and_keeps_retries_idempotent(committed_records):
    database, folder_id, foreign_id, document_id = committed_records
    repository = GoogleDriveRepository(database, DriveUser('42', '0' * 32))
    assert repository.owns_folder(folder_id, "42")
    assert not repository.owns_folder(foreign_id, "42")
    for _ in range(2):
        repository.associate_document_with_folder(folder_id, document_id, "42")
    for unavailable in (foreign_id, uuid4().hex):
        with pytest.raises(NotFoundError, match="Document or folder is no longer available"):
            repository.associate_document_with_folder(unavailable, document_id, "42")
    with database.session() as session:
        assert session.scalar(text("SELECT count(*) FROM document_folder_items WHERE document_id=:id"), {"id": document_id}) == 1


@pytest.mark.postgres
def test_repository_reports_missing_document_without_sql_details(committed_records):
    database, folder_id, _, _ = committed_records
    with pytest.raises(NotFoundError, match="Document or folder is no longer available"):
        GoogleDriveRepository(database, DriveUser('42', '0' * 32)).associate_document_with_folder(folder_id, uuid4().hex, "42")


@pytest.mark.postgres
def test_drive_writer_obeys_library_transaction_lock(committed_records):
    database, folder_id, _, document_id = committed_records
    started = Event()
    pid = []

    def writer():
        # Capture the real writer connection, not a separate observer connection.
        from sqlalchemy import event

        def capture(connection, cursor, statement, parameters, context, executemany):
            if "drive_associate_document" in statement:
                pid.append(connection.connection.driver_connection.info.backend_pid)
                started.set()

        event.listen(database._engine, "before_cursor_execute", capture)
        try:
            GoogleDriveRepository(database, DriveUser('42', '0' * 32)).associate_document_with_folder(folder_id, document_id, "42")
        finally:
            event.remove(database._engine, "before_cursor_execute", capture)

    with database.session() as blocker:
        blocker.execute(text("""SELECT pg_advisory_xact_lock(hashtextextended(
            'blandskron.library.document:' || :owner || ':' || :document, 0))"""), {"owner": "42", "document": document_id})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(writer)
            try:
                assert started.wait(3), "Drive bypassed the shared lock protocol"
                deadline = monotonic() + 3
                with database.session() as observer:
                    while not observer.scalar(text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid[0]}):
                        assert not future.done()
                        assert monotonic() < deadline
                        sleep(0.01)
                    assert observer.scalar(text("SELECT count(*) FROM document_folder_items WHERE document_id=:id"), {"id": document_id}) == 0
            finally:
                blocker.rollback()
            future.result(timeout=4)
    with database.session() as session:
        assert session.scalar(text("SELECT count(*) FROM document_folder_items WHERE document_id=:id"), {"id": document_id}) == 1


class ImportRepository:
    def ensure_connection_current(self, version):
        pass

    def check_identity(self):
        pass

    def __init__(self, owned=True, association_error=None):
        self.owned, self.association_error = owned, association_error
        self.files, self.associations = [], []
        self.connection_reads = 0

    def owns_folder(self, folder_id, owner):
        return self.owned

    def get_connection(self, owner):
        self.connection_reads += 1
        return SimpleNamespace(version=1,)

    def create_import(self, *args):
        return SimpleNamespace(import_id="synthetic-import")

    def add_import_file(self, import_id, payload):
        record = SimpleNamespace(import_file_id=str(len(self.files)), **payload)
        self.files.append(record)
        return record

    def update_import_file(self, identifier, payload):
        record = self.files[int(identifier)]
        for key, value in payload.items():
            setattr(record, key, value)
        return record

    def associate_document_with_folder(self, **payload):
        if self.association_error:
            raise self.association_error
        self.associations.append(payload)

    def finish_import(self, identifier, processed, failed, status, error):
        return SimpleNamespace(processed_files=processed, failed_files=failed, status=status, error_message=error)

    def list_import_files(self, identifier):
        return self.files


class SyntheticGoogleClient:
    def __init__(self):
        self.downloads = 0

    def download_file(self, *args):
        self.downloads += 1
        return SimpleNamespace(filename="synthetic.txt", mime_type="text/plain", content=b"Synthetic",
                               export_mime_type=None, metadata=SimpleNamespace(web_view_link=None, mime_type="text/plain"))


class SyntheticUploadClient:
    def __init__(self):
        self.uploads = 0

    def upload(self, **payload):
        self.uploads += 1
        return {"document_id": "synthetic-document", "status": "PROCESSED"}


def use_case(repository):
    google, upload = SyntheticGoogleClient(), SyntheticUploadClient()
    service = ManageGoogleDriveImports(repository, google, upload, None, SimpleNamespace(max_import_files=5))
    service._valid_access_token = lambda *args: "synthetic"
    return service, google, upload


def request(folder="synthetic-folder"):
    return GoogleDriveImportRequest(files=[GoogleDriveFileRequest(file_id="synthetic-file")], folder_id=folder)


def test_foreign_folder_is_rejected_before_provider_calls():
    repository = ImportRepository(owned=False)
    service, google, upload = use_case(repository)
    with pytest.raises(NotFoundError, match="Folder not found"):
        service.import_files("42", "synthetic", request())
    assert repository.connection_reads == google.downloads == upload.uploads == 0
    assert repository.files == []


@pytest.mark.parametrize("error", [NotFoundError("Folder disappeared"), RuntimeError("Synthetic private SQL detail")])
def test_folder_failure_keeps_upload_and_reports_partial_completion(error):
    repository = ImportRepository(association_error=error)
    service, google, upload = use_case(repository)
    result, files = service.import_files("42", "synthetic", request())
    assert result.status == "PARTIAL" and result.processed_files == 1 and result.failed_files == 0
    assert result.error_message == "Algunos documentos se importaron sin poder agregarse a la carpeta seleccionada."
    assert files[0].status == "COMPLETED" and files[0].document_id == "synthetic-document"
    assert files[0].metadata_["folder_association"] == {"status": "FAILED", "folder_id": "synthetic-folder"}
    assert files[0].error_message == "Documento importado, pero no se pudo agregar a la carpeta seleccionada."
    assert google.downloads == upload.uploads == 1


@pytest.mark.parametrize("folder_id", [None, "synthetic-folder"])
def test_successful_imports_preserve_completion(folder_id):
    repository = ImportRepository()
    service, _, _ = use_case(repository)
    result, files = service.import_files("42", "synthetic", request(folder_id))
    assert result.status == "COMPLETED" and result.error_message is None
    assert files[0].error_message is None
    assert len(repository.associations) == (1 if folder_id else 0)


def test_missing_uploaded_document_id_cannot_silently_skip_association():
    repository = ImportRepository()
    service, _, upload = use_case(repository)
    upload.upload = lambda **payload: {"status": "PROCESSED"}
    result, files = service.import_files("42", "synthetic", request())
    assert result.status == "PARTIAL" and result.error_message
    assert files[0].metadata_["folder_association"]["status"] == "FAILED"
    assert repository.associations == []
