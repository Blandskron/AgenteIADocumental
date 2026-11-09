from uuid import uuid4
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as SchemaValidationError

from app.application.use_cases.manage_google_drive_imports import ManageGoogleDriveImports
from app.interfaces.api.v1.schemas.google_drive_schema import GoogleDriveImportRequest
from app.shared.errors import ValidationError


@pytest.mark.parametrize("count", [0, 26])
def test_http_schema_rejects_out_of_range_batches(count):
    with pytest.raises(SchemaValidationError):
        GoogleDriveImportRequest(operation_id=str(uuid4()), files=[{"file_id": f"synthetic-{index}"} for index in range(count)])


@pytest.mark.parametrize("count", [1, 25])
def test_http_schema_accepts_batch_boundaries(count):
    request = GoogleDriveImportRequest(operation_id=str(uuid4()), files=[{"file_id": f"synthetic-{index}"} for index in range(count)])
    assert len(request.files) == count


class NoSideEffects:
    def __getattr__(self, name):
        raise AssertionError("Rejected batches must not access persistence or providers.")


@pytest.mark.parametrize("count", [0, 3])
def test_configured_limit_rejects_whole_batch_before_any_side_effect(count):
    boundary = NoSideEffects()
    service = ManageGoogleDriveImports(boundary, boundary, boundary, None, SimpleNamespace(max_import_files=2))
    payload = SimpleNamespace(files=[object() for _ in range(count)], folder_id="synthetic-folder")
    with pytest.raises(ValidationError):
        service.import_files("42", "synthetic", payload)


@pytest.mark.parametrize("metadata", [{"owner_user_id": "42"}, {"source": "forged"}, {"x": "a"*513},
    {"x": float("inf")}, {"x": [1]*33}, {"x": {"y": {"z": {"nested": {"too": "deep"}}}}}])
def test_metadata_is_bounded_and_cannot_override_authority(metadata):
    with pytest.raises(SchemaValidationError):
        GoogleDriveImportRequest(operation_id=str(uuid4()), files=[{"file_id": "synthetic"}], metadata=metadata)


def test_duplicate_ids_and_missing_operation_are_rejected():
    with pytest.raises(SchemaValidationError):
        GoogleDriveImportRequest(operation_id=str(uuid4()), files=[{"file_id": "synthetic"}]*2)
    with pytest.raises(SchemaValidationError):
        GoogleDriveImportRequest(files=[{"file_id": "synthetic"}])
