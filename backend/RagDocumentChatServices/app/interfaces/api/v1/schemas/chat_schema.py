from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.shared.constants import MAX_DOCUMENT_IDS, MAX_IDENTIFIER_LENGTH, MAX_QUESTION_LENGTH


Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_IDENTIFIER_LENGTH, pattern=r"^[^\x00]+$")]
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_LENGTH, pattern=r"^[^\x00]+$")]


class ChatAskRequest(BaseModel):
    question: Question
    session_id: Identifier | None = None
    document_ids: list[Identifier] = Field(default_factory=list, max_length=MAX_DOCUMENT_IDS)


class ChatSourceResponse(BaseModel):
    document_id: str
    chunk_id: str
    content: str
    score: float
    filename: str | None = None


class ChatAskResponse(BaseModel):
    answer: str
    sources: list[ChatSourceResponse]
