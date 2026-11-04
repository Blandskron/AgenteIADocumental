from app.application.documents.ports import DocumentSearchRepository
from app.domain.documents import DocumentSearchResult


class SearchDocuments:
    def __init__(self, repository: DocumentSearchRepository) -> None:
        self._repository = repository

    def execute(
        self,
        query: str | None = None,
        status: str | None = None,
        mime_type: str | None = None,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "created_desc",
    ) -> DocumentSearchResult:
        return self._repository.search(
            query=query,
            status=status,
            mime_type=mime_type,
            source=source,
            limit=max(1, min(limit, 100)),
            offset=max(0, offset),
            sort=sort,
        )
