import json

import httpx
import pytest
from openai import OpenAI

from app.application.chat.use_cases.ask_document_chat import ASSISTANT_ERROR_ANSWER, AskDocumentChat
from app.domain.chat import ChatMessage, MessageRole
from app.domain.embeddings import SearchResult
from app.infrastructure.ai import llm_provider_groq
from app.infrastructure.ai.llm_provider_groq import GroqLLMProvider
from app.shared.errors import ExternalServiceError


CONTEXT = [SearchResult("synthetic-document", "chunk-1", 0, "El contrato de prueba dura 97 días.", 1.0, "fixture.txt")]


def completion(choices):
    return {"id": "fixture", "object": "chat.completion", "created": 0, "model": "fixture-model", "choices": choices}


@pytest.fixture
def provider_factory(monkeypatch):
    def build(respond):
        requests = []

        def handle(request):
            requests.append(request)
            return respond(request)

        transport = httpx.MockTransport(handle)

        def client(**kwargs):
            return OpenAI(**kwargs, http_client=httpx.Client(transport=transport, timeout=kwargs["timeout"]))

        monkeypatch.setattr(llm_provider_groq, "OpenAI", client)
        return GroqLLMProvider("synthetic-test-key", "fixture-model", 80, 0.3, 4), requests

    return build


def test_sends_expected_payload_and_returns_answer(provider_factory):
    provider, requests = provider_factory(lambda _: httpx.Response(200, json=completion([{
        "index": 0, "finish_reason": "stop",
        "message": {"role": "assistant", "content": "El plazo es de 97 días."},
    }])))
    answer = provider.answer_with_context(
        "¿Cuánto dura?", CONTEXT, [ChatMessage(MessageRole.USER, "Pregunta anterior")], mode="summary",
    )
    assert answer == "El plazo es de 97 días."
    request, = requests
    assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer synthetic-test-key"
    assert request.extensions["timeout"]["read"] == 4
    payload = json.loads(request.content)
    assert payload["model"] == "fixture-model"
    assert payload["max_completion_tokens"] == 80
    assert payload["temperature"] == 0.3
    assert "resumen" in payload["messages"][0]["content"]
    assert "Pregunta anterior" in payload["messages"][1]["content"]
    assert "97 días" in payload["messages"][1]["content"]
    assert "¿Cuánto dura?" in payload["messages"][1]["content"]


@pytest.mark.parametrize("choices", [
    [],
    [{"index": 0, "message": {"role": "assistant", "content": None}}],
    [{"index": 0, "message": {"role": "assistant", "content": "  "}}],
])
def test_empty_responses_are_external_errors(provider_factory, choices):
    provider, requests = provider_factory(lambda _: httpx.Response(200, json=completion(choices)))
    with pytest.raises(ExternalServiceError, match="respuesta vacía"):
        provider.answer_with_context("Question", CONTEXT)
    assert len(requests) == 1


@pytest.mark.parametrize(("status", "message"), [(401, "clave"), (429, "generar"), (503, "generar")])
def test_http_errors_are_sanitized_and_not_retried(provider_factory, status, message):
    provider, requests = provider_factory(lambda _: httpx.Response(status, json={"error": {"message": "private detail"}}))
    with pytest.raises(ExternalServiceError, match=message) as error:
        provider.answer_with_context("Question", CONTEXT)
    assert "private detail" not in str(error.value)
    assert len(requests) == 1


def test_timeout_is_not_retried(provider_factory):
    def respond(request):
        raise httpx.ReadTimeout("Synthetic timeout", request=request)

    provider, requests = provider_factory(respond)
    with pytest.raises(ExternalServiceError, match="tiempo configurado"):
        provider.answer_with_context("Question", CONTEXT)
    assert len(requests) == 1


def test_missing_key_does_not_create_client(monkeypatch):
    def unexpected_client(**_):
        pytest.fail("Unexpected HTTP client")

    monkeypatch.setattr(llm_provider_groq, "OpenAI", unexpected_client)
    with pytest.raises(ExternalServiceError, match="GROQ_API_KEY"):
        GroqLLMProvider(" ", "fixture-model", 80, 0.3, 4).answer_with_context("Question", CONTEXT)


def test_provider_failure_returns_chat_fallback(provider_factory):
    provider, requests = provider_factory(lambda _: httpx.Response(200, json=completion([])))

    class SyntheticSearch:
        def execute(self, question, document_ids):
            return CONTEXT

    answer = AskDocumentChat(SyntheticSearch(), provider).execute("¿Cuánto dura?")
    assert answer.answer == ASSISTANT_ERROR_ANSWER
    assert answer.sources == []
    assert len(requests) == 1
