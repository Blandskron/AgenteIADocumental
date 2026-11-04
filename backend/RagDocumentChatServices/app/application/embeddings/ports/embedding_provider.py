from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed_text(self, text: str) -> list[float]:
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...
