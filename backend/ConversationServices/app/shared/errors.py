class AppError(Exception):
    """Base application error."""


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class ExternalServiceError(AppError):
    pass


class DatabaseError(AppError):
    pass


class ExtractionError(AppError):
    pass
