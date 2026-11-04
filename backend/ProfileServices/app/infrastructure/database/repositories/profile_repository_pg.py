from sqlalchemy.orm import Session

from app.infrastructure.database.models import UserProfileModel


class UserProfileRepositoryPg:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_id(self, user_id: str) -> UserProfileModel | None:
        return self._session.query(UserProfileModel).filter(UserProfileModel.user_id == user_id).first()

    def create_or_update(
        self,
        user_id: str,
        email: str | None = None,
        phone_number: str | None = None,
        profile_picture_url: str | None = None,
        additional_info: dict | None = None,
    ) -> UserProfileModel:
        profile = self.get_by_user_id(user_id)
        if profile is None:
            profile = UserProfileModel(
                user_id=user_id,
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

    def list_all(self) -> list[UserProfileModel]:
        return self._session.query(UserProfileModel).all()
