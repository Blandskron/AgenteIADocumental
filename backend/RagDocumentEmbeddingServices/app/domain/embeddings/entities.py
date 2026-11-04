from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentChunk:
    document_id: str
    chunk_index: int
    content: str
    metadata: dict | None = None
