from __future__ import annotations

import json
import os
from typing import Any

from providers.base import ModelResponse, ToolCall


class OpenAIProvider:
    """OpenAI Chat Completions provider with normalized tool_calls output."""

    def __init__(
        self,
        *,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
        api_key_default: str | None = None,
        request_timeout: float | None = None,
        max_retries: int | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.api_key_env = api_key_env
        self.api_key_default = api_key_default
        self.base_url = base_url
        self.default_model = default_model
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.max_tokens = max_tokens

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        tool_choice: Any | None = None,
    ) -> ModelResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install live provider dependency first: pip install openai") from exc

        api_key = os.getenv(self.api_key_env) or self.api_key_default
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {self.api_key_env}")

        client_options: dict[str, Any] = {"api_key": api_key, "base_url": self.base_url}
        # Keep cloud SDK defaults unless a local-compatible provider opts in.
        if self.request_timeout is not None:
            client_options["timeout"] = self.request_timeout
        if self.max_retries is not None:
            client_options["max_retries"] = self.max_retries
        client = OpenAI(**client_options)
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens

        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        for call in msg.tool_calls or []:
            raw_args = call.function.arguments or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                # Small models often emit malformed JSON. Keep the call so eval grades it
                # as a wrong-argument failure instead of hiding it as provider_error.
                args = {"_invalid_json_arguments": raw_args}
            if not isinstance(args, dict):
                args = {"_invalid_json_arguments": raw_args}
            calls.append(ToolCall(name=call.function.name, args=args))
        return ModelResponse(text=msg.content, tool_calls=calls, raw=resp)
