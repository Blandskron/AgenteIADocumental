from dataclasses import dataclass
from math import isfinite
import re

from app.application.embeddings.ports.embedding_provider import EmbeddingProvider
from app.application.embeddings.ports.vector_repository import VectorRepository
from app.domain.embeddings import DocumentChunk
from app.shared.constants import EMBEDDING_BATCH_SIZE, EMBEDDING_DIMENSIONS, MAX_DOCUMENT_CHUNKS
from app.shared.errors import ExternalServiceError, ExtractionError

PAGE_MARKER_RE = re.compile(r"^\[page\s+(\d+)\]$", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class _TextSegment:
    content: str
    page: int | None
    section: str | None


class CreateDocumentEmbeddings:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_repository: VectorRepository,
        chunk_size: int,
        chunk_overlap: int,
        embedding_model: str,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_repository = vector_repository
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._embedding_model = embedding_model

    def execute(self, document_id: str, text: str, metadata: dict | None = None) -> list[DocumentChunk]:
        base_metadata = dict(metadata) if metadata else None
        chunks: list[DocumentChunk] = []
        for index, segment in enumerate(self._split_structured(text)):
            chunk_metadata: dict | None = dict(base_metadata) if base_metadata is not None else None
            if segment.page is not None or segment.section is not None:
                chunk_metadata = dict(chunk_metadata or {})
                if segment.page is not None:
                    chunk_metadata["page"] = segment.page
                if segment.section is not None:
                    chunk_metadata["section"] = segment.section
            chunks.append(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=index,
                    content=segment.content,
                    metadata=chunk_metadata,
                )
            )
        vectors = []
        for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = [chunk.content for chunk in chunks[start:start + EMBEDDING_BATCH_SIZE]]
            embeddings = self._embedding_provider.embed_batch(batch)
            if len(embeddings) != len(batch) or any(
                len(vector) != EMBEDDING_DIMENSIONS or not all(isfinite(value) for value in vector)
                for vector in embeddings
            ):
                raise ExternalServiceError("Embedding provider returned invalid vectors.")
            vectors.extend(embeddings)
        self._vector_repository.replace_document_chunks(
            document_id=document_id,
            chunks=chunks,
            vectors=vectors,
            embedding_model=self._embedding_model,
        )
        return chunks

    def _split_text(self, text: str) -> list[str]:
        return [segment.content for segment in self._split_structured(text)]

    def _split_structured(self, text: str) -> list[_TextSegment]:
        cleaned = text.strip()
        if not cleaned:
            raise ExtractionError("Document contains no extractable text.")

        blocks = self._extract_blocks(cleaned)
        if not blocks:
            raise ExtractionError("Document contains no extractable text.")

        segments: list[_TextSegment] = []
        current_parts: list[str] = []
        current_len = 0
        current_page: int | None = None
        current_section: str | None = None

        def flush() -> None:
            nonlocal current_parts, current_len
            if not current_parts:
                return
            joined = "\n\n".join(current_parts).strip()
            if joined:
                segments.append(_TextSegment(content=joined, page=current_page, section=current_section))
                if len(segments) > MAX_DOCUMENT_CHUNKS:
                    raise ExtractionError("Document exceeds the indexing chunk limit.")
            current_parts = []
            current_len = 0

        for block_text, page, section, is_heading in blocks:
            # Start a new chunk when crossing page or heading boundaries if buffer already has content.
            if current_parts and (
                (page is not None and current_page is not None and page != current_page)
                or (is_heading and section != current_section)
            ):
                flush()

            if not current_parts:
                current_page = page
                current_section = section

            if len(block_text) > self._chunk_size:
                if current_parts:
                    flush()
                current_page = page
                current_section = section
                for piece in self._split_oversized_block(block_text):
                    segments.append(_TextSegment(content=piece, page=page, section=section))
                    if len(segments) > MAX_DOCUMENT_CHUNKS:
                        raise ExtractionError("Document exceeds the indexing chunk limit.")
                continue

            separator_len = 2 if current_parts else 0
            if current_parts and current_len + separator_len + len(block_text) > self._chunk_size:
                prev_tail = self._overlap_tail("\n\n".join(current_parts))
                flush()
                current_page = page
                current_section = section
                if prev_tail and len(prev_tail) + 2 + len(block_text) <= self._chunk_size:
                    current_parts = [prev_tail, block_text]
                    current_len = len(prev_tail) + 2 + len(block_text)
                else:
                    current_parts = [block_text]
                    current_len = len(block_text)
            else:
                current_parts.append(block_text)
                current_len += separator_len + len(block_text)

        flush()
        return segments

    def _extract_blocks(self, text: str) -> list[tuple[str, int | None, str | None, bool]]:
        """Parses `[page N]` markers and Markdown/DOCX headings into structured blocks."""
        blocks: list[tuple[str, int | None, str | None, bool]] = []
        active_page: int | None = None
        active_section: str | None = None

        raw_paragraphs = re.split(r"\n{2,}", text)
        for raw_para in raw_paragraphs:
            para = raw_para.strip()
            if not para:
                continue
            lines = para.split("\n")
            first_line = lines[0].strip()
            page_match = PAGE_MARKER_RE.match(first_line)
            if page_match:
                active_page = int(page_match.group(1))
                rest = "\n".join(lines[1:]).strip()
                if not rest:
                    continue
                para = rest
                lines = para.split("\n")
                first_line = lines[0].strip()

            heading_match = HEADING_RE.match(first_line)
            if heading_match:
                active_section = heading_match.group(2).strip()[:160]
                blocks.append((para, active_page, active_section, True))
            else:
                blocks.append((para, active_page, active_section, False))

        return blocks

    def _overlap_tail(self, text: str) -> str:
        if self._chunk_overlap <= 0 or not text:
            return ""
        tail = text[-self._chunk_overlap :].strip()
        if not tail:
            return ""
        space_idx = tail.find(" ")
        if 0 < space_idx < len(tail) - 1 and len(text) > self._chunk_overlap:
            return tail[space_idx + 1 :].strip()
        return tail

    def _split_oversized_block(self, block: str) -> list[str]:
        sentences = [s.strip() for s in SENTENCE_BOUNDARY_RE.split(block) if s.strip()]
        if len(sentences) > 1 and all(len(s) <= self._chunk_size for s in sentences):
            pieces: list[str] = []
            buf: list[str] = []
            buf_len = 0
            for sentence in sentences:
                sep = 1 if buf else 0
                if buf and buf_len + sep + len(sentence) > self._chunk_size:
                    joined = " ".join(buf).strip()
                    pieces.append(joined)
                    tail = self._overlap_tail(joined)
                    if tail and len(tail) + 1 + len(sentence) <= self._chunk_size:
                        buf = [tail, sentence]
                        buf_len = len(tail) + 1 + len(sentence)
                    else:
                        buf = [sentence]
                        buf_len = len(sentence)
                else:
                    buf.append(sentence)
                    buf_len += sep + len(sentence)
            if buf:
                pieces.append(" ".join(buf).strip())
            return pieces

        # Fallback to character window for continuous text without sentence boundaries.
        pieces = []
        start = 0
        while start < len(block):
            end = min(start + self._chunk_size, len(block))
            piece = block[start:end].strip()
            if piece:
                pieces.append(piece)
                if len(pieces) > MAX_DOCUMENT_CHUNKS:
                    raise ExtractionError("Document exceeds the indexing chunk limit.")
            if end == len(block):
                break
            start = max(end - self._chunk_overlap, start + 1)
        return pieces
