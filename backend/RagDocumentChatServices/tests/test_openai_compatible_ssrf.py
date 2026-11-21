import pytest

from app.infrastructure.ai.llm_provider_openai_compatible import validate_provider_base_url


def test_ssrf_allowlist_blocks_private_loopback_metadata_and_plain_http():
    assert validate_provider_base_url("https://api.groq.com/openai/v1/") == "https://api.groq.com/openai/v1"
    assert validate_provider_base_url("http://127.0.0.1:11434/v1", allow_local=True) == "http://127.0.0.1:11434/v1"

    blocked = [
        "http://api.example.com/v1",
        "https://localhost/v1",
        "https://127.0.0.1/v1",
        "https://169.254.169.254/latest/meta-data",
        "https://10.0.0.5/v1",
        "https://192.168.1.10/v1",
        "https://user:pass@api.example.com/v1",
    ]
    for url in blocked:
        with pytest.raises(ValueError):
            validate_provider_base_url(url)

