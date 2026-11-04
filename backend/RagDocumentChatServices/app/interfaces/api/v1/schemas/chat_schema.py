from pydantic import BaseModel, Field


class ChatAskRequest(BaseModel):
    question: str = Field(min_length=1)
    session_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)


class ChatSourceResponse(BaseModel):
    document_id: str
    chunk_id: str
    content: str
    score: float
    filename: str | None = None


class ChatAskResponse(BaseModel):
    answer: str
    sources: list[ChatSourceResponse]
