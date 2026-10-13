"""
Phase 9 configuration — every tunable number for the explanation layer.

Environment variables (data-pipeline/.env):
    LLM_PROVIDER   gemini | mock          (default: mock — runs with no key or network)
    LLM_MODEL      Gemini model name      (default below)
    LLM_API_KEY    Gemini API key         (never commit it)
"""

import os

DEFAULT_PROVIDER: str = "mock"
DEFAULT_GEMINI_MODEL: str = "gemini-3.5-flash"

TEMPERATURE: float = 0.2           # low → consistent phrasing
MAX_OUTPUT_TOKENS: int = 160
REQUEST_TIMEOUT_S: int = 30        # per API call
MAX_RETRIES: int = 1               # one retry after a rejection or API error, then fallback
RETRY_BACKOFF_S: float = 2.0       # pause before retrying after an API error (rate limits)
MAX_CHARS: int = 400               # guardrail: longer outputs are rejected

# Elasticity → plain-English band (computed in code, never by the LLM).
#   |elasticity| <  1.0         → "not very price-sensitive"
#   1.0 ≤ |elasticity| ≤ 1.5    → "moderately price-sensitive"
#   |elasticity| >  1.5         → "highly price-sensitive"
SENSITIVITY_MODERATE_FROM: float = 1.0
SENSITIVITY_HIGH_ABOVE: float = 1.5

# Words the LLM must not use (jargon the audience should not see).
BANNED_TERMS: list[str] = ["β", "beta", "log-log", "coefficient", "elasticity of"]


def provider() -> str:
    return os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()


def model_name() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_GEMINI_MODEL).strip()
