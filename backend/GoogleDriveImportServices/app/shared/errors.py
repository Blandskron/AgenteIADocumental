class AppError(Exception):
    pass


class ValidationError(AppError):
    pass


class NotFoundError(AppError):
    pass


class GoogleDriveError(AppError):
    pass


class ExternalServiceError(AppError):
    pass


class DriveConflictError(AppError):
    pass


class ReauthorizationRequired(AppError):
    pass
