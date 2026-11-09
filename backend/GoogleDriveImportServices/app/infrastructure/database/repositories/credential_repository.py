import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import delete, func, select, text

from app.infrastructure.database.models import GoogleDriveConnectionModel as Connection, GoogleDriveOAuthAttempt as Attempt
from app.shared.errors import DriveConflictError, ReauthorizationRequired, ValidationError


class CredentialRepository:
    def _locked_connection(self, session):
        session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('blandskron.drive.credentials:'||:owner,0))"),
                        {"owner": self._user.user_id})
        row = session.scalar(select(Connection).where(Connection.owner_user_id == self._user.user_id).with_for_update())
        if row is None:
            row = Connection(owner_user_id=self._user.user_id,access_token_encrypted="",grant_status="DISCONNECTED")
            session.add(row)
            session.flush()
        return row

    def _now(self, session):
        return session.scalar(select(func.clock_timestamp()))

    def _binding(self):
        return hashlib.sha256((self._user.user_id+":"+self._user.fingerprint+":"+(self._user.tenant_id or "")).encode()).hexdigest()

    def create_attempt(self, challenge, configuration_hash):
        state = secrets.token_urlsafe(32)
        with self._session() as session:
            row = self._locked_connection(session)
            now = self._now(session)
            self._check_lease(session,row,now)
            if row.grant_status == "REVOKE_PENDING":
                raise DriveConflictError("Complete revocation before reconnecting.")
            session.execute(delete(Attempt).where(Attempt.owner_user_id == self._user.user_id,
                            (Attempt.expires_at <= now) | (Attempt.consumed_at.is_not(None))))
            count=session.scalar(select(func.count()).select_from(Attempt).where(Attempt.owner_user_id==self._user.user_id))
            if count >= 10:
                raise DriveConflictError("Too many outstanding authorization attempts.")
            session.add(Attempt(state_hash=hashlib.sha256(state.encode()).hexdigest(),owner_user_id=self._user.user_id,
                                identity_binding=self._binding(),configuration_hash=configuration_hash,code_challenge=challenge,
                                connection_version=row.version,expires_at=now+timedelta(minutes=5)))
            session.commit()
        return state

    def _check_lease(self, session, row, now):
        if row.lease_token:
            if row.lease_until > now:
                raise DriveConflictError("Drive credentials are busy.")
            # Never repeat an ambiguous expired refresh automatically.
            row.grant_status = "REVOKE_PENDING" if row.lease_kind == "REVOKE" else "REAUTH_REQUIRED"
            row.lease_token=row.lease_kind=row.lease_until=None
            row.version+=1
            session.commit()
            raise DriveConflictError("An interrupted credential operation requires review.")

    def consume_attempt(self, state, verifier_challenge, configuration_hash):
        with self._session() as session:
            row=self._locked_connection(session)
            now=self._now(session)
            self._check_lease(session,row,now)
            attempt=session.scalar(select(Attempt).where(Attempt.state_hash==hashlib.sha256(state.encode()).hexdigest(),
                                   Attempt.owner_user_id==self._user.user_id).with_for_update())
            if (attempt is None or attempt.consumed_at is not None or attempt.expires_at<=now
                or not hmac.compare_digest(attempt.identity_binding,self._binding())
                or not hmac.compare_digest(attempt.code_challenge,verifier_challenge)
                or not hmac.compare_digest(attempt.configuration_hash,configuration_hash)):
                raise ValidationError("Invalid or expired authorization attempt.")
            if attempt.connection_version!=row.version or row.grant_status=="REVOKE_PENDING":
                raise DriveConflictError("The connection changed; begin authorization again.")
            attempt.consumed_at=now
            self._set_lease(row,"CONNECT",now)
            session.commit()
            return row

    def _set_lease(self,row,kind,now):
        row.lease_token=secrets.token_urlsafe(32)
        row.lease_kind=kind
        row.lease_until=now+timedelta(seconds=300)

    def claim_credentials(self, expected_version, kind):
        with self._session() as session:
            row=self._locked_connection(session)
            now=self._now(session)
            self._check_lease(session,row,now)
            if row.version!=expected_version:
                raise DriveConflictError("Drive connection changed.")
            if kind=="REFRESH" and row.grant_status!="ACTIVE":
                raise ReauthorizationRequired("Drive authorization is required.")
            if kind=="REVOKE":
                if row.grant_status=="DISCONNECTED":
                    return None
                row.grant_status="REVOKE_PENDING"
            self._set_lease(row,kind,now)
            session.commit()
            return row

    def finish_credentials(self, lease, values):
        with self._session() as session:
            row=self._locked_connection(session)
            if (row.version!=lease.version or row.lease_token!=lease.lease_token or row.lease_until<=self._now(session)):
                raise DriveConflictError("Credential operation is no longer current.")
            for name,value in values.items():
                setattr(row,name,value)
            row.version+=1
            row.lease_token=row.lease_kind=row.lease_until=None
            session.commit()
            return row

    def fail_credentials(self, lease, status):
        with self._session() as session:
            row=self._locked_connection(session)
            if row.version==lease.version and row.lease_token==lease.lease_token:
                row.grant_status=status
                row.version+=1
                row.lease_token=row.lease_kind=row.lease_until=None
                session.commit()

    def ensure_connection_current(self, version):
        with self._session() as session:
            row=session.scalar(select(Connection).where(Connection.owner_user_id==self._user.user_id))
            if row is None or row.version!=version or row.grant_status!="ACTIVE" or row.lease_token:
                raise DriveConflictError("Drive connection changed.")
