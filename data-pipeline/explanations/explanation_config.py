import os

DEFAULT_PROVIDER: str = "mock"
DEFAULT_GEMINI_MODEL: str = "gemini-3.5-flash"

TEMPERATURE: float = 0.2
MAX_OUTPUT_TOKENS: int = 160
REQUEST_TIMEOUT_S: int = 30
MAX_RETRIES: int = 1
RETRY_BACKOFF_S: float = 2.0
MAX_CHARS: int = 400

SENSITIVITY_MODERATE_FROM: float = 1.0
SENSITIVITY_HIGH_ABOVE: float = 1.5

BANNED_TERMS: list[str] = ["\u03b2", "beta", "log-log", "coefficient", "elasticity of"]


def provider() -> str:
    return os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()


def model_name() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_GEMINI_MODEL).strip()
