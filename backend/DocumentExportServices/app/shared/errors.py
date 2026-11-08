class AppError(Exception):
    """Base application error."""


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class ExportGenerationError(AppError):
    pass


class ExportConflictError(AppError):
    pass


class ExportExpiredError(AppError):
    pass


class ExportLimitError(ValidationError):
    pass

