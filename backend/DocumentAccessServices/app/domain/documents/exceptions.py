from app.shared.errors import NotFoundError
from app.shared.errors import ValidationError


class DocumentNotFoundError(NotFoundError):
    pass


class DocumentDownloadNotAllowedError(ValidationError):
    pass
