from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config.settings import Settings
from app.shared.errors import GoogleDriveError, ValidationError


GOOGLE_NATIVE_EXPORTS = {
    "application/vnd.google-apps.document": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "application/vnd.google-apps.spreadsheet": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
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
    content: bytes
    filename: str
    mime_type: str
    export_mime_type: str | None
    metadata: DriveFileMetadata


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
        with httpx.Client(timeout=self._settings.request_timeout_seconds) as client:
            response = client.get("https://www.googleapis.com/drive/v3/about", params={"fields": "user(permissionId,emailAddress)"}, headers=self._auth_headers(access_token))
        if response.status_code >= 400:
            raise GoogleDriveError("Google Drive identity lookup failed.")
        return response.json().get("user", {})

    def revoke(self, token: str):
        with httpx.Client(timeout=self._settings.request_timeout_seconds) as client:
            response = client.post("https://oauth2.googleapis.com/revoke", data={"token": token})
        if response.status_code == 200:
            return
        if response.status_code == 400 and response.json().get("error") == "invalid_token":
            return
        raise GoogleDriveError("Google grant revocation is pending.")

    def download_file(self, access_token: str, file_id: str, export_mime_type: str | None = None) -> DownloadedDriveFile:
        metadata = self.get_file_metadata(access_token, file_id)
        selected_export_mime_type = export_mime_type
        filename = metadata.name
        url = f"{self._settings.google_drive_api_base_url}/files/{file_id}"
        params = {"alt": "media", "supportsAllDrives": "true"}

        if metadata.mime_type.startswith("application/vnd.google-apps."):
            default_export = GOOGLE_NATIVE_EXPORTS.get(metadata.mime_type)
            if not default_export and not selected_export_mime_type:
                raise GoogleDriveError(f"Unsupported Google Workspace file type: {metadata.mime_type}")
            selected_export_mime_type = selected_export_mime_type or default_export[0]
            extension = default_export[1] if default_export and selected_export_mime_type == default_export[0] else ""
            filename = self._ensure_extension(filename, extension)
            url = f"{self._settings.google_drive_api_base_url}/files/{file_id}/export"
            params = {"mimeType": selected_export_mime_type}

        with httpx.Client(timeout=self._settings.request_timeout_seconds) as client:
            response = client.get(url, params=params, headers=self._auth_headers(access_token))

        if response.status_code >= 400:
            raise GoogleDriveError(f"Google Drive download failed for {file_id}: HTTP {response.status_code}")

        return DownloadedDriveFile(
            content=response.content,
            filename=filename,
            mime_type=selected_export_mime_type or metadata.mime_type,
            export_mime_type=selected_export_mime_type,
            metadata=metadata,
        )

    def get_file_metadata(self, access_token: str, file_id: str) -> DriveFileMetadata:
        params = {
            "fields": "id,name,mimeType,size,webViewLink",
            "supportsAllDrives": "true",
        }
        with httpx.Client(timeout=self._settings.request_timeout_seconds) as client:
            response = client.get(
                f"{self._settings.google_drive_api_base_url}/files/{file_id}",
                params=params,
                headers=self._auth_headers(access_token),
            )
        if response.status_code >= 400:
            raise GoogleDriveError(f"Google Drive metadata failed for {file_id}: HTTP {response.status_code}")
        payload = response.json()
        return DriveFileMetadata(
            file_id=payload.get("id", file_id),
            name=payload.get("name") or file_id,
            mime_type=payload.get("mimeType") or "application/octet-stream",
            size_bytes=int(payload["size"]) if payload.get("size") else None,
            web_view_link=payload.get("webViewLink"),
        )

    def _post_token(self, payload: dict) -> dict:
        if not self._settings.google_oauth_client_id or not self._settings.google_oauth_client_secret:
            raise ValidationError("Google OAuth client credentials are not configured.")
        with httpx.Client(timeout=self._settings.request_timeout_seconds) as client:
            response = client.post(self._settings.google_oauth_token_url, data=payload)
        if response.status_code >= 400:
            raise GoogleDriveError(f"Google OAuth token request failed: HTTP {response.status_code}")
        return response.json()

    @staticmethod
    def _auth_headers(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    @staticmethod
    def _ensure_extension(filename: str, extension: str) -> str:
        if not extension or filename.lower().endswith(extension):
            return filename
        return f"{filename}{extension}"
