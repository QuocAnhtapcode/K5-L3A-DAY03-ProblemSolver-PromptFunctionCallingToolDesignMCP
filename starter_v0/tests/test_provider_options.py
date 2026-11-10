import sys
from types import SimpleNamespace

import pytest

from providers.openai_provider import OpenAIProvider


@pytest.fixture
def provider_requests(monkeypatch):
    requests = []

    def complete(**kwargs):
        requests.append(kwargs)
        message = SimpleNamespace(content="done", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace()
    client.chat = SimpleNamespace()
    client.chat.completions = SimpleNamespace(create=complete)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **kwargs: client))
    monkeypatch.delenv("MODEL_MAX_TOKENS", raising=False)
    return requests


def test_provider_keeps_default_request_without_token_budget(provider_requests):
    provider = OpenAIProvider(api_key_default="test-key")

    provider.complete([{"role": "user", "content": "hello"}])

    assert "max_tokens" not in provider_requests[0]


def test_provider_passes_configured_token_budget(monkeypatch, provider_requests):
    monkeypatch.setenv("MODEL_MAX_TOKENS", "512")
    provider = OpenAIProvider(api_key_default="test-key")

    provider.complete([{"role": "user", "content": "hello"}])

    assert provider_requests[0]["max_tokens"] == 512


@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_provider_rejects_invalid_token_budget(monkeypatch, provider_requests, value):
    monkeypatch.setenv("MODEL_MAX_TOKENS", value)
    provider = OpenAIProvider(api_key_default="test-key")

    with pytest.raises(ValueError):
        provider.complete([{"role": "user", "content": "hello"}])

    assert provider_requests == []
