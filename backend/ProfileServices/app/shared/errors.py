class AppError(Exception):
    """Base application error."""


class ConflictError(AppError):
    pass
