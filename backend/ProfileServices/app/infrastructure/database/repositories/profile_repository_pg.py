from sqlalchemy.orm import Session
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.infrastructure.database.models import UserProfileModel
from app.shared.errors import ConflictError


class UserProfileRepositoryPg:
    def __init__(self, session: Session, owner_id: str) -> None:
        self._session = session
        self._owner_id = owner_id

    @property
    def owner_id(self) -> str:
        return self._owner_id

    def get_own(self) -> UserProfileModel | None:
        return self._session.query(UserProfileModel).filter(UserProfileModel.user_id == self._owner_id).first()

    def read_avatar(self, version: int | None = None) -> bytes | None:
        query = select(UserProfileModel.avatar_data).where(
            UserProfileModel.user_id == self._owner_id, UserProfileModel.avatar_ready.is_(True),
        )
        if version is not None:
            query = query.where(UserProfileModel.version == version)
        content = self._session.scalar(query)
        self._session.commit()  # Release the Auth share lock before sending image bytes.
        return content

    def create_or_update(
        self,
        expected_version: int,
        changes: dict,
    ) -> UserProfileModel:
        if "additional_info" in changes and changes["additional_info"] is None:
            changes = {**changes, "additional_info": {}}
        if expected_version == 0:
            statement = insert(UserProfileModel).values(user_id=self._owner_id, **changes).on_conflict_do_nothing(
                index_elements=[UserProfileModel.user_id],
            )
        else:
            statement = update(UserProfileModel).where(
                UserProfileModel.user_id == self._owner_id, UserProfileModel.version == expected_version,
            ).values(**changes, version=UserProfileModel.version + 1)
        profile = self._session.scalars(statement.returning(UserProfileModel),
                                        execution_options={"populate_existing": True}).first()
        if profile is None:
            raise ConflictError("Profile changed. Reload it before saving again.")
        self._session.commit()
        return profile
