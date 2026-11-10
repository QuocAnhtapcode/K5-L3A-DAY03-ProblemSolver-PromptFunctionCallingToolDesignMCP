"""Offline checks for bounded local requests and unchanged cloud requests."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from providers.ollama_provider import OllamaProvider
from providers.openai_provider import OpenAIProvider
from providers.openrouter_provider import OpenRouterProvider


@pytest.fixture
def sdk(monkeypatch):
    recorded = {"clients": [], "requests": [], "raw_args": '{"question":"URL?"}'}

    class Client:
        def __init__(self, **options):
            recorded["clients"].append(options)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **options):
            recorded["requests"].append(options)
            message = SimpleNamespace(
                content=None,
                tool_calls=[SimpleNamespace(function=SimpleNamespace(
                    name="clarify", arguments=recorded["raw_args"],
                ))],
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
    for name in ("OLLAMA_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_TIMEOUT", "OLLAMA_MAX_TOKENS"):
        monkeypatch.delenv(name, raising=False)
    return recorded


def test_ollama_bounds_request_without_real_api_key(sdk):
    response = OllamaProvider().complete(
        [{"role": "user", "content": "Read this article."}],
        [{"type": "function", "function": {"name": "clarify"}}],
        tool_choice="required",
    )

    assert sdk["clients"] == [{
        "api_key": "ollama", "base_url": "http://localhost:11434/v1",
        "timeout": 120.0, "max_retries": 0,
    }]
    assert sdk["requests"][0]["max_tokens"] == 512
    assert sdk["requests"][0]["model"] == "qwen2.5:7b"
    assert sdk["requests"][0]["tool_choice"] == "required"
    assert response.tool_calls[0].args == {"question": "URL?"}


def test_ollama_local_overrides_and_explicit_model_are_forwarded(sdk, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "90")
    monkeypatch.setenv("OLLAMA_MAX_TOKENS", "256")

    OllamaProvider().complete([], model="qwen2.5:3b")

    assert sdk["clients"][0]["base_url"] == "http://127.0.0.1:1234/v1"
    assert sdk["clients"][0]["timeout"] == 90.0
    assert sdk["requests"][0]["max_tokens"] == 256
    assert sdk["requests"][0]["model"] == "qwen2.5:3b"
    assert "tool_choice" not in sdk["requests"][0]


@pytest.mark.parametrize("raw", ['{broken', '["not", "an", "object"]', '"text"', '42'])
def test_local_invalid_json_arguments_remain_visible_for_eval(raw, sdk):
    sdk["raw_args"] = raw

    response = OllamaProvider().complete([])

    assert response.tool_calls[0].name == "clarify"
    assert response.tool_calls[0].args == {"_invalid_json_arguments": raw}


@pytest.mark.parametrize("provider_name", ["openai", "openrouter"])
def test_cloud_requests_keep_sdk_defaults_and_no_local_token_cap(provider_name, sdk, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-openai")
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-test-openrouter")
    provider = OpenAIProvider() if provider_name == "openai" else OpenRouterProvider()

    provider.complete([], tool_choice="required")

    assert "timeout" not in sdk["clients"][0]
    assert "max_retries" not in sdk["clients"][0]
    assert "max_tokens" not in sdk["requests"][0]
    assert sdk["requests"][0]["tool_choice"] == "required"
