from functools import lru_cache
from os import environ

from sentence_transformers import SentenceTransformer

from app.shared.errors import ExternalServiceError

MODEL_NAME = "intfloat/multilingual-e5-small"


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    return SentenceTransformer(
        environ.get("E5_MODEL_DIR", "/opt/e5-model"),
        device="cpu",
        local_files_only=True,
        model_kwargs={"use_safetensors": True},
    )


class LocalEmbeddingProvider:
    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = _load_model().encode(
                [f"passage: {text}" for text in texts],
                normalize_embeddings=True,
            )
            return vectors.tolist()
        except (OSError, RuntimeError, ValueError) as exc:
            raise ExternalServiceError("No se pudieron generar los embeddings locales.") from exc
