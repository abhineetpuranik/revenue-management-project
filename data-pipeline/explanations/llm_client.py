"""
LLM clients — Phase 9.

A deliberately tiny interface:  client.generate(system_prompt, user_prompt) -> str

    GeminiClient    Google Gemini via the official google-genai SDK
    MockLLMClient   deterministic, offline — renders the template fallback from
                    the JSON in the prompt. Used for tests, demos and for
                    teammates without an API key.

get_client() picks one from LLM_PROVIDER (gemini | mock).
No LangChain, no agents, no retrieval — one prompt in, one text out.
"""

from __future__ import annotations

import json
import os
import re

from explanations.explanation_config import (MAX_OUTPUT_TOKENS, REQUEST_TIMEOUT_S, TEMPERATURE,
                                             model_name, provider)
from explanations.fallback import fallback_text


class LLMError(RuntimeError):
    """Any failure talking to the LLM (network, auth, quota, timeout, empty reply)."""


class LLMClient:
    name: str = "base"

    def generate(self, system_prompt: str, user_prompt: str) -> str:  # pragma: no cover
        raise NotImplementedError


class MockLLMClient(LLMClient):
    """Deterministic stand-in: returns the template sentence for the payload in the prompt."""
    name = "mock"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        m = re.search(r"JSON:\s*(\{.*\})\s*$", user_prompt, flags=re.S)
        if not m:
            raise LLMError("mock: no JSON payload in prompt")
        payload = json.loads(m.group(1))
        entity_type = "pricing" if "action" in payload else "segment"
        return fallback_text(entity_type, payload)


class GeminiClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        api_key = api_key or os.getenv("LLM_API_KEY")
        if not api_key:
            raise LLMError("LLM_API_KEY is not set (data-pipeline/.env). "
                           "Set LLM_PROVIDER=mock to run without a key.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:                       # pragma: no cover
            raise LLMError("google-genai is not installed: pip install -r requirements.txt") from exc
        self._types = types
        self.model = model or model_name()
        self.name = self.model
        try:
            http = types.HttpOptions(timeout=REQUEST_TIMEOUT_S * 1000)   # milliseconds
            self._client = genai.Client(api_key=api_key, http_options=http)
        except TypeError:                                 # older SDKs without timeout option
            self._client = genai.Client(api_key=api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=self._types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                ),
            )
        except Exception as exc:                          # network, quota, auth, timeout ...
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        text = getattr(resp, "text", None)
        if not text:
            raise LLMError("empty response (possibly blocked or truncated)")
        return text.strip()


def get_client() -> LLMClient:
    p = provider()
    if p == "mock":
        return MockLLMClient()
    if p == "gemini":
        return GeminiClient()
    raise ValueError(f"Unknown LLM_PROVIDER={p!r} (use 'gemini' or 'mock')")
