from app.shared.errors import NotFoundError, ValidationError


class DocumentNotFoundError(NotFoundError):
    pass


class InvalidDocumentSelectionError(ValidationError):
    pass
