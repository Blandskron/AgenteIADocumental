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


class ImportSourceConflict(AppError):
    pass


class ImportConnectionConflict(AppError):
    pass


class ProviderStatusError(GoogleDriveError):
    def __init__(self, status, code=None):
        self.status = status
        self.code = code
        super().__init__("Unexpected provider status.")


class UploadRejected(ExternalServiceError):
    pass
