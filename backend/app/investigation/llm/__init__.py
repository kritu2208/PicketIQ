"""LLM Investigation package for evidence-grounded root-cause analysis."""

from app.investigation.llm.providers import (
    BaseLLMProvider,
    MockLLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    get_llm_provider,
)
from app.investigation.llm.validator import validate_investigation_conclusion
__all__ = [
    "BaseLLMProvider",
    "MockLLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "get_llm_provider",
    "validate_investigation_conclusion",
    "explain_investigation",
    "investigate_and_explain",
]


def __getattr__(name: str):
    if name in ("explain_investigation", "investigate_and_explain"):
        import app.investigation.llm.investigator as inv
        return getattr(inv, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

