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


class PayloadTooLarge(AppError):
    pass


class ConflictError(AppError):
    pass


class DocumentRelationConflict(ConflictError):
    """Creation rolled back because its tenant/area relation no longer exists."""
