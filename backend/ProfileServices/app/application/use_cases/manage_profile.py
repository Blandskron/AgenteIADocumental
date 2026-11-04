from app.domain.entities import UserProfile
from app.infrastructure.database.repositories.profile_repository_pg import UserProfileRepositoryPg


class ManageProfile:
    def __init__(self, repository: UserProfileRepositoryPg) -> None:
        self._repository = repository

    def get_profile(self, user_id: str) -> UserProfile:
        model = self._repository.get_by_user_id(user_id)
        if model is None:
            return UserProfile(user_id=user_id)
        return self._to_entity(model)

    def update_profile(
        self,
        user_id: str,
        email: str | None = None,
        phone_number: str | None = None,
        profile_picture_url: str | None = None,
        additional_info: dict | None = None,
    ) -> UserProfile:
        model = self._repository.create_or_update(
            user_id=user_id,
            email=email,
            phone_number=phone_number,
            profile_picture_url=profile_picture_url,
            additional_info=additional_info,
        )
        return self._to_entity(model)

    def list_profiles(self) -> list[UserProfile]:
        models = self._repository.list_all()
        return [self._to_entity(m) for m in models]

    def _to_entity(self, model) -> UserProfile:
        return UserProfile(
            profile_id=str(model.profile_id),
            user_id=model.user_id,
            email=model.email,
            phone_number=model.phone_number,
            profile_picture_url=model.profile_picture_url,
            additional_info=model.additional_info,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
