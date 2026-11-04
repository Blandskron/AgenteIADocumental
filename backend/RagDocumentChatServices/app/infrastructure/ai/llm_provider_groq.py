from openai import APIError, AuthenticationError, OpenAI

from app.domain.chat import ChatMessage
from app.domain.embeddings import SearchResult
from app.shared.constants import MAX_IDENTIFIER_LENGTH
from app.shared.errors import ExternalServiceError


class GroqLLMProvider:
    def __init__(
        self, api_key: str, model: str, max_tokens: int, temperature: float, timeout_seconds: int
    ) -> None:
        self._client = (
            OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1", timeout=timeout_seconds)
            if api_key.strip()
            else None
        )
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    def answer_with_context(
        self,
        question: str,
        context: list[SearchResult],
        history: list[ChatMessage] | None = None,
        mode: str = "qa",
    ) -> str:
        if self._client is None:
            raise ExternalServiceError("Configura GROQ_API_KEY para usar el chat documental.")
        context_text = self._format_context(context)
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_completion_tokens=self._max_tokens,
                temperature=self._temperature,
                messages=[
                    {
                        "role": "system",
                        "content": self._system_prompt(mode),
                    },
                    {
                        "role": "user",
                        "content": self._user_prompt(question, context_text, history),
                    },
                ],
            )
            content = response.choices[0].message.content
            if not content or not content.strip():
                raise ExternalServiceError("Groq devolvió una respuesta vacía.")
            return content
        except AuthenticationError as exc:
            raise ExternalServiceError("La clave de Groq configurada no es válida.") from exc
        except APIError as exc:
            raise ExternalServiceError("No se pudo generar una respuesta con Groq.") from exc

    def _system_prompt(self, mode: str) -> str:
        base = (
            "Eres Blandskron Documental, un asistente virtual documental. Responde siempre en lenguaje natural, "
            "conversacional y util para una persona que esta leyendo documentos. No respondas como motor "
            "de busqueda ni como validador de contexto. Usa el contexto documental disponible y explica "
            "con tus propias palabras. Si falta informacion, dilo al final con tacto."
        )
        if mode == "summary":
            return (
                f"{base} Cuando te pidan un resumen, sintetiza los fragmentos entregados aunque sean parciales: "
                "identifica el tema central, las ideas principales, conceptos clave y una conclusion breve. "
                "No digas que no hay contexto si recibiste fragmentos del documento."
            )
        return (
            f"{base} Para preguntas puntuales, responde directo primero y luego agrega el contexto necesario. "
            "Si el documento no permite responder con certeza, explica que parte si se puede inferir."
        )

    def _user_prompt(
        self,
        question: str,
        context_text: str,
        history: list[ChatMessage] | None,
    ) -> str:
        history_text = self._format_history(history or [])
        return (
            f"Historial reciente de la conversacion:\n{history_text}\n\n"
            f"Contexto documental recuperado:\n{context_text}\n\n"
            f"Solicitud del usuario:\n{question}"
        )

    def _format_history(self, history: list[ChatMessage]) -> str:
        if not history:
            return "No hay historial previo relevante."
        return "\n".join(f"{message.role.value}: {message.content}" for message in history)

    def _format_context(self, context: list[SearchResult]) -> str:
        if not context:
            return "No hay contexto documental relevante."
        return "\n\n".join(
            f"[Fuente {index + 1}] archivo={(item.filename or 'documento')[:MAX_IDENTIFIER_LENGTH]} "
            f"document_id={item.document_id[:MAX_IDENTIFIER_LENGTH]} chunk={item.chunk_index} "
            f"score={item.score:.4f}\n{item.content}"
            for index, item in enumerate(context)
        )
