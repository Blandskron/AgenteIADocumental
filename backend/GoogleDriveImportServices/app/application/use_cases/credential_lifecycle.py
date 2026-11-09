import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

from app.shared.errors import DriveConflictError, ReauthorizationRequired, ValidationError


class CredentialLifecycle:
    def _configuration_hash(self):
        values = [self._settings.google_oauth_client_id, self._settings.google_oauth_redirect_uri,
                  self._settings.google_oauth_scope_list]
        return hashlib.sha256(json.dumps(values).encode()).hexdigest()

    def auth_url(self, owner_user_id, code_challenge):
        self._repository.check_identity()
        state = self._repository.create_attempt(code_challenge, self._configuration_hash())
        return {"authorization_url": self._google_client.build_authorization_url(state, code_challenge),
                "state": state, "redirect_uri": self._settings.google_oauth_redirect_uri}

    def connect(self, owner_user_id, code, state, code_verifier):
        challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest()).decode().rstrip("=")
        lease = self._repository.consume_attempt(state, challenge, self._configuration_hash())
        try:
            payload = self._google_client.exchange_code(code, code_verifier)
            values = self._credential_values(payload)
            self._repository.check_identity()
            account = self._google_client.get_userinfo(payload["access_token"])
            subject = account.get("permissionId")
            if not isinstance(subject, str) or not subject or len(subject) > 256:
                raise ValidationError("Google Drive account identity is unavailable.")
            if not values["refresh_token_encrypted"]:
                if (lease.grant_status != "ACTIVE" or lease.provider_account_id != subject
                        or lease.oauth_client_id != self._settings.google_oauth_client_id):
                    raise ReauthorizationRequired("Offline authorization is required.")
                self._token_cipher.decrypt(lease.refresh_token_encrypted)
                if not lease.refresh_token_encrypted:
                    raise ReauthorizationRequired("Offline authorization is required.")
                values["refresh_token_encrypted"] = lease.refresh_token_encrypted
            values.update(provider_account_id=subject, provider_account_email=account.get("emailAddress"),
                          oauth_client_id=self._settings.google_oauth_client_id, grant_status="ACTIVE")
            self._repository.finish_credentials(lease, values)
        except Exception:
            self._repository.fail_credentials(lease, lease.grant_status)
            raise
        return self.connected_status(owner_user_id)

    def connected_status(self, owner_user_id):
        connection = self._repository.get_connection(owner_user_id)
        status = connection.grant_status if connection else "DISCONNECTED"
        if connection and status == "ACTIVE" and self._settings.google_drive_enabled:
            if connection.oauth_client_id != self._settings.google_oauth_client_id:
                status = "REAUTH_REQUIRED"
            else:
                try:
                    self._token_cipher.decrypt(connection.access_token_encrypted)
                except ReauthorizationRequired:
                    status = "REAUTH_REQUIRED"
        return {"connected": status == "ACTIVE", "enabled": self._settings.google_drive_enabled,
                "grant_status": status, "version": connection.version if connection else 0,
                "busy": bool(connection and connection.lease_token and connection.lease_until > datetime.now(UTC)),
                "provider_account_email": connection.provider_account_email if connection else None,
                "provider_account_id": connection.provider_account_id if connection else None,
                "oauth_client_id": self._settings.google_oauth_client_id,
                "picker_app_id": self._settings.google_picker_app_id,
                "scopes": connection.scopes if connection else [],
                "expires_at": connection.expires_at if connection else None}

    def disconnect(self, owner_user_id, version):
        lease = self._repository.claim_credentials(version, "REVOKE")
        if lease is None:
            return self.connected_status(owner_user_id)
        try:
            if not self._settings.google_drive_enabled or self._token_cipher is None:
                raise ReauthorizationRequired("Revocation requires the configured encryption key.")
            token = self._token_cipher.decrypt(lease.refresh_token_encrypted or lease.access_token_encrypted)
            if not token:
                raise ReauthorizationRequired("Stored grant cannot be revoked automatically.")
            self._google_client.revoke(token)
            self._repository.finish_credentials(lease, {
                "grant_status": "DISCONNECTED", "access_token_encrypted": "",
                "refresh_token_encrypted": None, "provider_account_id": None,
                "provider_account_email": None, "oauth_client_id": None,
                "scopes": [], "expires_at": None, "metadata_": {},
            })
        except DriveConflictError:
            raise
        except Exception:
            self._repository.fail_credentials(lease, "REVOKE_PENDING")
        return self.connected_status(owner_user_id)

    def _credential_values(self, payload):
        if not isinstance(payload, dict) or str(payload.get("token_type", "")).lower() != "bearer":
            raise ValidationError("Unexpected Google token response.")
        for key in ("access_token", "refresh_token"):
            value = payload.get(key)
            if (key == "access_token" or value is not None) and (
                not isinstance(value, str) or not 1 <= len(value) <= 8192
                or not value.isascii() or any(ord(char) < 33 or ord(char) > 126 for char in value)
            ):
                raise ValidationError("Unexpected Google token response.")
        expires = payload.get("expires_in")
        if type(expires) is not int or not 1 <= expires <= 86400:
            raise ValidationError("Unexpected Google token expiration.")
        scopes = payload.get("scope", " ".join(self._settings.google_oauth_scope_list))
        if not isinstance(scopes, str) or scopes.split() != self._settings.google_oauth_scope_list:
            raise ValidationError("Unexpected Google authorization scope.")
        return {"access_token_encrypted": self._token_cipher.encrypt(payload["access_token"]),
                "refresh_token_encrypted": self._token_cipher.encrypt(payload.get("refresh_token")),
                "expires_at": datetime.now(UTC) + timedelta(seconds=expires),
                "scopes": scopes.split()}

    def _valid_access_token(self, owner_user_id, connection):
        self._repository.ensure_connection_current(connection.version)
        if connection.oauth_client_id != self._settings.google_oauth_client_id:
            raise ReauthorizationRequired("Google authorization must be renewed.")
        access_token = self._token_cipher.decrypt(connection.access_token_encrypted)
        if not connection.expires_at or connection.expires_at <= datetime.now(UTC) + timedelta(minutes=2):
            lease = self._repository.claim_credentials(connection.version, "REFRESH")
            try:
                refresh = self._token_cipher.decrypt(lease.refresh_token_encrypted)
                if not refresh:
                    raise ReauthorizationRequired("Offline authorization is required.")
                payload = self._google_client.refresh_access_token(refresh)
                values = self._credential_values(payload)
                account = self._google_client.get_userinfo(payload["access_token"])
                if account.get("permissionId") != lease.provider_account_id:
                    raise ReauthorizationRequired("Google Drive identity changed.")
                values["refresh_token_encrypted"] = values["refresh_token_encrypted"] or lease.refresh_token_encrypted
                updated = self._repository.finish_credentials(lease, values)
                connection.version = updated.version
                access_token = payload["access_token"]
            except Exception:
                self._repository.fail_credentials(lease, "REAUTH_REQUIRED")
                raise
        if not access_token:
            raise ReauthorizationRequired("Google authorization must be renewed.")
        return access_token
