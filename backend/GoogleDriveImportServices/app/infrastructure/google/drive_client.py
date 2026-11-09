import json
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from time import monotonic
from typing import BinaryIO
from urllib.parse import urlencode

import httpx

from app.config.settings import Settings
from app.infrastructure.google.bounded_transport import provider_json, read_response
from app.shared.import_limits import FILE_ID, MAX_FILE_BYTES, MIME_EXTENSIONS, safe_filename
from app.shared.errors import GoogleDriveError, ValidationError


GOOGLE_NATIVE_EXPORTS = {
    "application/vnd.google-apps.document": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "application/vnd.google-apps.spreadsheet": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}


@dataclass
class DriveFileMetadata:
    file_id: str
    name: str
    mime_type: str
    size_bytes: int | None
    web_view_link: str | None


@dataclass
class DownloadedDriveFile:
    content: BinaryIO
    filename: str
    mime_type: str
    export_mime_type: str | None
    metadata: DriveFileMetadata
    size_bytes: int

    def close(self):
        self.content.close()


class GoogleDriveClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_authorization_url(self, state: str, code_challenge: str) -> str:
        if not self._settings.google_oauth_client_id:
            raise ValidationError("Google OAuth client id is not configured.")

        query = urlencode(
            {
                "client_id": self._settings.google_oauth_client_id,
                "redirect_uri": self._settings.google_oauth_redirect_uri,
                "response_type": "code",
                "scope": " ".join(self._settings.google_oauth_scope_list),
                "access_type": "offline",
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "prompt": "consent select_account",
                "state": state,
            },
        )
        return f"{self._settings.google_oauth_authorize_url}?{query}"

    def exchange_code(self, code: str, code_verifier: str) -> dict:
        payload = {
            "code": code,
            "code_verifier": code_verifier,
            "client_id": self._settings.google_oauth_client_id,
            "client_secret": self._settings.google_oauth_client_secret,
            "redirect_uri": self._settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        }
        return self._post_token(payload)

    def refresh_access_token(self, refresh_token: str) -> dict:
        payload = {
            "client_id": self._settings.google_oauth_client_id,
            "client_secret": self._settings.google_oauth_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        return self._post_token(payload)

    def get_userinfo(self, access_token: str) -> dict:
        payload = provider_json("GET", "https://www.googleapis.com/drive/v3/about",
                                params={"fields": "user(permissionId,emailAddress)"}, headers=self._auth_headers(access_token),
                                timeout=self._settings.request_timeout_seconds)
        user = payload.get("user")
        if not isinstance(user, dict):
            raise GoogleDriveError("Google Drive identity lookup failed.")
        return user

    def revoke(self, token: str):
        deadline = monotonic() + self._settings.request_timeout_seconds
        try:
            with httpx.Client(timeout=self._settings.request_timeout_seconds, follow_redirects=False, trust_env=False) as client:
                with client.stream("POST", "https://oauth2.googleapis.com/revoke", data={"token": token}, headers={"Accept-Encoding": "identity"}) as response:
                    with SpooledTemporaryFile(max_size=32768, mode="w+b") as body:
                        read_response(response, body, 32768, deadline, allowed_statuses=(200, 400))
                        if response.status_code == 200:
                            return
                        value = json.load(body)
                        if isinstance(value, dict) and value.get("error") == "invalid_token":
                            return
        except Exception:
            raise GoogleDriveError("Google grant revocation is pending.") from None
        raise GoogleDriveError("Google grant revocation is pending.")

    def download_file(self, access_token: str, file_id: str, export_mime_type: str | None = None, *, maximum=MAX_FILE_BYTES, deadline=None, budget=None) -> DownloadedDriveFile:
        deadline = min(deadline or monotonic() + 120, monotonic() + 120)
        metadata = self.get_file_metadata(access_token, file_id, deadline=deadline)
        selected = None
        if metadata.mime_type.startswith("application/vnd.google-apps."):
            default = GOOGLE_NATIVE_EXPORTS.get(metadata.mime_type)
            allowed = {"application/pdf", default[0]} if default else set()
            if not default or (export_mime_type and export_mime_type not in allowed):
                raise ValidationError("Unsupported Google Workspace export format.")
            selected = export_mime_type or default[0]
            url = f"{self._settings.google_drive_api_base_url}/files/{file_id}/export"
            params = {"mimeType": selected}
        else:
            if metadata.mime_type not in MIME_EXTENSIONS or export_mime_type:
                raise ValidationError("Unsupported Google Drive document format.")
            if metadata.size_bytes is not None and metadata.size_bytes > maximum:
                raise GoogleDriveError("Google Drive file exceeds supported limits.")
            url = f"{self._settings.google_drive_api_base_url}/files/{file_id}"
            params = {"alt": "media", "supportsAllDrives": "true"}
        if monotonic() >= deadline:
            raise GoogleDriveError("Google Drive time budget is exhausted.")
        filename = safe_filename(metadata.name, selected or metadata.mime_type)
        body = SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
        try:
            with httpx.Client(timeout=min(self._settings.request_timeout_seconds, max(0.1, deadline-monotonic())), follow_redirects=False, trust_env=False) as client:
                with client.stream("GET", url, params=params, headers={**self._auth_headers(access_token), "Accept-Encoding": "identity"}) as response:
                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if content_type and content_type not in {selected or metadata.mime_type, "application/octet-stream"}:
                        raise GoogleDriveError("Unexpected Google Drive media type.")
                    size = read_response(response, body, min(maximum, MAX_FILE_BYTES), deadline, budget)
            if size == 0:
                raise GoogleDriveError("Google Drive file is empty.")
            return DownloadedDriveFile(body, filename, selected or metadata.mime_type, selected, metadata, size)
        except Exception:
            body.close()
            raise

    def get_file_metadata(self, access_token: str, file_id: str, *, deadline=None) -> DriveFileMetadata:
        if not FILE_ID.fullmatch(file_id):
            raise ValidationError("Invalid Google Drive file identifier.")
        payload = provider_json("GET", f"{self._settings.google_drive_api_base_url}/files/{file_id}",
                                params={"fields": "id,name,mimeType,size,webViewLink", "supportsAllDrives": "true"},
                                headers=self._auth_headers(access_token), timeout=self._settings.request_timeout_seconds, deadline=deadline)
        if (payload.get("id") != file_id or not isinstance(payload.get("name"), str)
                or not isinstance(payload.get("mimeType"), str) or len(payload["mimeType"]) > 128):
            raise GoogleDriveError("Invalid Google Drive metadata.")
        size = payload.get("size")
        if size is not None and (not isinstance(size, str) or not size.isascii() or not size.isdigit() or len(size) > 18):
            raise GoogleDriveError("Invalid Google Drive file size.")
        # Do not propagate arbitrary provider URLs into persisted metadata.
        return DriveFileMetadata(file_id, payload["name"], payload["mimeType"], int(size) if size is not None else None, None)

    def _post_token(self, payload: dict) -> dict:
        if not self._settings.google_oauth_client_id or not self._settings.google_oauth_client_secret:
            raise ValidationError("Google OAuth client credentials are not configured.")
        return provider_json("POST", self._settings.google_oauth_token_url, data=payload,
                             timeout=self._settings.request_timeout_seconds)

    @staticmethod
    def _auth_headers(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}
