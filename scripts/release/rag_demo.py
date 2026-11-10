"""Verification-only Groq transport; real retrieval/embedding code, no external AI key."""

import json
import sys

import httpx
import uvicorn
from openai import OpenAI

sys.path.insert(0, "/app")
from app.interfaces.api.v1 import dependencies  # noqa: E402
from app.infrastructure.ai.llm_provider_groq import GroqLLMProvider  # noqa: E402


def respond(request):
    assert (
        request.url.host == "api.groq.com"
        and request.url.path == "/openai/v1/chat/completions"
    )
    payload = json.loads(request.content)
    prompt = payload["messages"][-1]["content"]
    context = prompt.split("Contexto documental recuperado:\n", 1)[1].split(
        "\n\nSolicitud del usuario:", 1
    )[0]
    answer = (
        "El contrato sintético dura 97 días."
        if "97" in context
        else "Sin contexto documental autorizado."
    )
    return httpx.Response(
        200,
        json={
            "id": "synthetic-demo",
            "object": "chat.completion",
            "created": 0,
            "model": payload["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": answer},
                    "finish_reason": "stop",
                }
            ],
        },
    )


def provider(settings):
    instance = GroqLLMProvider(
        "",
        settings.groq_chat_model,
        settings.chat_completion_max_tokens,
        settings.chat_completion_temperature,
        settings.chat_completion_timeout_seconds,
    )
    instance._client = OpenAI(
        api_key="synthetic-demo-only",
        base_url="https://api.groq.com/openai/v1",
        max_retries=0,
        http_client=httpx.Client(
            transport=httpx.MockTransport(respond), trust_env=False
        ),
    )
    return instance


dependencies.build_llm_provider = provider
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
