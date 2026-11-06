from sqlalchemy.orm import Session

from app.infrastructure.database.models import UserProfileModel


class UserProfileRepositoryPg:
    def __init__(self, session: Session, owner_id: str) -> None:
        self._session = session
        self._owner_id = owner_id

    @property
    def owner_id(self) -> str:
        return self._owner_id

    def get_own(self) -> UserProfileModel | None:
        return self._session.query(UserProfileModel).filter(UserProfileModel.user_id == self._owner_id).first()

    def create_or_update(
        self,
        email: str | None = None,
        phone_number: str | None = None,
        profile_picture_url: str | None = None,
        additional_info: dict | None = None,
    ) -> UserProfileModel:
        profile = self.get_own()
        if profile is None:
            profile = UserProfileModel(
                user_id=self._owner_id,
                email=email,
                phone_number=phone_number,
                profile_picture_url=profile_picture_url,
                additional_info=additional_info or {},
            )
            self._session.add(profile)
        else:
            if email is not None:
                profile.email = email
            if phone_number is not None:
                profile.phone_number = phone_number
            if profile_picture_url is not None:
                profile.profile_picture_url = profile_picture_url
            if additional_info is not None:
                profile.additional_info = additional_info

        self._session.commit()
        self._session.refresh(profile)
        return profile
