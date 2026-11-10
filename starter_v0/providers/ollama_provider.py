from __future__ import annotations

import os

from providers.openai_provider import OpenAIProvider


class OllamaProvider(OpenAIProvider):
    """Local small models via Ollama's OpenAI-compatible endpoint (no API key needed).

    Also works with any other local OpenAI-compatible server (LM Studio, llama.cpp
    server, vLLM) by overriding OLLAMA_BASE_URL.

    Requests have a 120-second timeout, no SDK retries, and a 512-token generation
    cap so one local failure cannot silently occupy an eval for several minutes.
    OLLAMA_TIMEOUT and OLLAMA_MAX_TOKENS can override these local-only limits.
    """

    def __init__(self) -> None:
        super().__init__(
            api_key_env="OLLAMA_API_KEY",
            api_key_default="ollama",  # local server ignores the key, but the SDK requires one
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            default_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            request_timeout=float(os.getenv("OLLAMA_TIMEOUT", "120")),
            max_retries=0,
            max_tokens=int(os.getenv("OLLAMA_MAX_TOKENS", "512")),
        )
