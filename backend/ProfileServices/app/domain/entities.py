from datetime import datetime
from typing import Any


class UserProfile:
    def __init__(
        self,
        user_id: str,
        email: str | None = None,
        phone_number: str | None = None,
        profile_picture_url: str | None = None,
        additional_info: dict[str, Any] | None = None,
        profile_id: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.profile_id = profile_id
        self.user_id = user_id
        self.email = email
        self.phone_number = phone_number
        self.profile_picture_url = profile_picture_url
        self.additional_info = additional_info or {}
        self.created_at = created_at
        self.updated_at = updated_at
