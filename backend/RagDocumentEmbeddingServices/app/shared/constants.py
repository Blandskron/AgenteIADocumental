DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 160
DEFAULT_VECTOR_SEARCH_LIMIT = 5
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024
MAX_UPLOAD_BODY_BYTES = MAX_DOCUMENT_BYTES + 128 * 1024
MAX_EXTRACTED_CHARACTERS = 1_000_000
EMBEDDING_DIMENSIONS = 384
EMBEDDING_BATCH_SIZE = 32
MAX_DOCUMENT_CHUNKS = 2048

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/tiff",
}
