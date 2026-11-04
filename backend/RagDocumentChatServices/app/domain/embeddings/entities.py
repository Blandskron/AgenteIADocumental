from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    document_id: str
    chunk_id: str
    chunk_index: int
    content: str
    score: float
    filename: str | None = None
    metadata: dict | None = None
