class AppError(Exception):
    """Base application error."""


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class ConflictError(AppError):
    pass
