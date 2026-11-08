from sqlalchemy import select, text
from app.config.security import read_public_key
from app.infrastructure.database.models import GoogleDriveOAuthAttempt, GoogleDriveConnectionModel, GoogleDriveImportModel, GoogleDriveImportFileModel


def check_dependencies(settings, session):
    read_public_key(settings.auth_jwt_public_key_path)
    for model in (GoogleDriveOAuthAttempt, GoogleDriveConnectionModel, GoogleDriveImportModel, GoogleDriveImportFileModel):
        session.execute(select(model).limit(0))
    for signature in ("drive_identity_is_current(bigint,text)", "drive_access_is_allowed(bigint,text)",
                      "drive_owns_folder(text,text)", "drive_associate_document(text,text,text)"):
        if not session.scalar(text("SELECT has_function_privilege(current_user,:signature,'EXECUTE')"),
                              {"signature": "public." + signature}):
            raise RuntimeError("Drive helper is unavailable.")
