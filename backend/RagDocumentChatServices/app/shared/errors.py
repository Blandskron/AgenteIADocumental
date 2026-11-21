class AppError(Exception):
    """Base application error."""


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class ExternalServiceError(AppError):
    def __init__(self, message: str, provider_status: str = "provider_error") -> None:
        super().__init__(message)
        self.provider_status = provider_status


class DatabaseError(AppError):
    pass


class ExtractionError(AppError):
    pass
