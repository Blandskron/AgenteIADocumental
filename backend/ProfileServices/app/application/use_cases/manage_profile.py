from app.domain.entities import UserProfile
from app.infrastructure.database.repositories.profile_repository_pg import UserProfileRepositoryPg


class ManageProfile:
    def __init__(self, repository: UserProfileRepositoryPg) -> None:
        self._repository = repository

    def get_profile(self) -> UserProfile:
        model = self._repository.get_own()
        if model is None:
            return UserProfile(user_id=self._repository.owner_id)
        return self._to_entity(model)

    def update_profile(
        self,
        expected_version: int,
        changes: dict,
    ) -> UserProfile:
        model = self._repository.create_or_update(
            expected_version=expected_version, changes=changes,
        )
        return self._to_entity(model)

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
            version=model.version,
        )
