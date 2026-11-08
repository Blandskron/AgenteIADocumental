from datetime import datetime
import json
import math
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from reportlab.pdfbase.ttfonts import TTFont


@lru_cache
def supported_characters():
    base = Path(__file__).parents[4] / "infrastructure/pdf/fonts"
    regular = TTFont("check-regular", str(base / "NotoSans-Regular.ttf"))
    bold = TTFont("check-bold", str(base / "NotoSans-Bold.ttf"))
    return set(regular.face.charToGlyph) & set(bold.face.charToGlyph)


def checked_text(value):
    value = unicodedata.normalize("NFC", value).replace("\t", "    ")
    for char in value:
        if char == "\n":
            continue
        if unicodedata.category(char).startswith("C") or ord(char) not in supported_characters():
            raise ValueError("Unsupported text character.")
    return value


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    document_id: str = Field(default="", max_length=128)
    chunk_id: str = Field(default="", max_length=128)
    filename: str = Field(default="", max_length=256)
    page: int | None = Field(default=None, ge=1, le=1_000_000, strict=True)
    page_number: int | None = Field(default=None, ge=1, le=1_000_000, strict=True)
    content: str = Field(default="", max_length=2000)
    snippet: str = Field(default="", max_length=2000)
    chunk: str = Field(default="", max_length=2000)
    score: float = Field(default=0, allow_inf_nan=False)

    @field_validator("document_id", "chunk_id", "filename", "content", "snippet", "chunk")
    @classmethod
    def valid_text(cls, value):
        return checked_text(value)


class ChatPdfExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=128)
    message_id: str | None = Field(default=None, min_length=1, max_length=128)
    title: str = Field(default="Respuesta documental", min_length=1, max_length=160)
    question: str = Field(default="", max_length=8000)
    answer: str = Field(min_length=1, max_length=50_000)
    sources: list[Source] = Field(default_factory=list, max_length=40)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "question", "answer", "conversation_id", "message_id")
    @classmethod
    def valid_text(cls, value):
        return checked_text(value) if value is not None else value

    @field_validator("metadata")
    @classmethod
    def valid_metadata(cls, value):
        nodes = 0
        def visit(item, depth):
            nonlocal nodes
            nodes += 1
            if depth > 4 or nodes > 256:
                raise ValueError("Metadata exceeds structural limits.")
            if type(item) is dict:
                for key, child in item.items():
                    if not isinstance(key, str) or len(key) > 64:
                        raise ValueError("Invalid metadata key.")
                    checked_text(key)
                    visit(child, depth + 1)
            elif type(item) is list:
                for child in item:
                    visit(child, depth + 1)
            elif type(item) is str:
                if len(item) > 2048:
                    raise ValueError("Metadata string too long.")
                checked_text(item)
            elif item is not None and (type(item) not in (int, float, bool)
                                       or (type(item) is int and not -(2**63) <= item < 2**63)
                                       or (type(item) is float and not math.isfinite(item))):
                raise ValueError("Invalid metadata scalar.")
        visit(value, 0)
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()) > 8192:
            raise ValueError("Metadata exceeds byte limit.")
        return value


class ExportResponse(BaseModel):
    export_id: str
    source_type: str
    source_id: str | None
    conversation_id: str | None
    message_id: str | None
    title: str
    format: str
    status: str
    filename: str
    mime_type: str
    file_size_bytes: int
    metadata: dict[str, Any]
    download_url: str
    created_at: datetime | None
    updated_at: datetime | None
    expires_at: datetime | None = None
    sha256: str | None = None


class ExportPage(BaseModel):
    items: list[ExportResponse]
    next_cursor: str | None
