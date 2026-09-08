"""Pluggable LLM Provider Abstraction for PicketIQ.

Supports:
- MockLLMProvider: Deterministic, evidence-grounded interpreter for tests and offline use
- OpenAIProvider: OpenAI and OpenAI-compatible endpoints (Groq, vLLM, Ollama, OpenRouter) via httpx
- AnthropicProvider: Anthropic Claude Messages API via httpx
- GeminiProvider: Google Generative Language API via httpx
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

import httpx

from app.config import (
    LLM_PROVIDER,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_BASE_URL,
    LLM_TEMPERATURE,
)

logger = logging.getLogger("picket_iq.investigation.llm.providers")


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    provider_name: str
    model_name: str

    @abstractmethod
    def generate_conclusion(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        """Generate a structured JSON investigation conclusion from prompts.

        Args:
            system_prompt: System instructions defining evidence grounding rules and output schema.
            user_prompt: Structured investigation context containing anomaly details and evidence chain.

        Returns:
            Dictionary matching the investigation conclusion schema.
        """
        pass


class MockLLMProvider(BaseLLMProvider):
    """Deterministic, evidence-grounded provider for automated testing and offline environments.

    Analyzes the provided investigation evidence prompt and synthesizes a structured,
    reproducible conclusion without invoking external network APIs.
    """

    def __init__(
        self,
        model_name: str = "mock-grounded-analyst",
        custom_response: Optional[Dict[str, Any]] = None,
    ):
        self.provider_name = "mock"
        self.model_name = model_name
        self.custom_response = custom_response

    def generate_conclusion(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        """Synthesize a structured conclusion strictly from the verified evidence context."""
        if self.custom_response is not None:
            return self.custom_response

        # Check for insufficient data signals in the user prompt
        if "INSUFFICIENT DATA" in user_prompt or "insufficient_data" in user_prompt:
            return {
                "root_cause": "Inconclusive / Insufficient Evidence",
                "explanation": (
                    "Available historical data was insufficient to establish a reliable baseline "
                    "or conclusively determine the driving operational factor behind this movement."
                ),
                "confidence": "low",
                "affected_segment": None,
                "evidence_references": [
                    "Step 1 (segment_breakdown): Insufficient baseline observations",
                    "Step 2 (check_seasonality): Insufficient same-weekday history",
                ],
                "recommended_action": (
                    "Allow additional daily observations to accumulate to establish a stable baseline "
                    "before drawing operational conclusions."
                ),
            }

        # Extract metric, date, and actuals from prompt
        metric_match = re.search(r"Metric\s*:\s*([^\n]+)", user_prompt)
        date_match = re.search(r"Date\s*:\s*([^\n]+)", user_prompt)
        z_match = re.search(r"Z-Score\s*:\s*([^\n]+)", user_prompt)
        top_seg_match = re.search(r"Top Contributor\s*:\s*([A-Za-z0-9_]+)", user_prompt)
        pct_contrib_match = re.search(r"Contribution\s*:\s*([0-9\.\+\-]+)%", user_prompt)
        seas_match = re.search(r"Is Seasonal\s*:\s*(True|False)", user_prompt)
        trend_match = re.search(r"Classification\s*:\s*([a-z_]+)", user_prompt)

        metric = metric_match.group(1).strip() if metric_match else "unknown_metric"
        dt = date_match.group(1).strip() if date_match else "target date"
        z_val = z_match.group(1).strip() if z_match else "0.0"
        top_seg = top_seg_match.group(1).strip() if top_seg_match else None
        pct_contrib = pct_contrib_match.group(1).strip() if pct_contrib_match else None
        is_seasonal = seas_match.group(1) == "True" if seas_match else False
        trend_class = trend_match.group(1).strip() if trend_match else "stable"

        # Evidence references grounded in the 3 steps
        evidence_references = [
            f"Step 1 (segment_breakdown): Top contributor was '{top_seg}' ({pct_contrib}% of total delta)"
            if top_seg and pct_contrib
            else "Step 1 (segment_breakdown): Regional contribution evaluated",
            f"Step 2 (check_seasonality): Seasonality evaluated (is_seasonal={is_seasonal})",
            f"Step 3 (get_recent_trend): Trajectory classified as '{trend_class}'",
        ]

        # Formulate grounded explanation
        seg_desc = f" heavily driven by region '{top_seg}'" if top_seg else ""
        seas_desc = (
            "consistent with regular weekly cyclical patterns"
            if is_seasonal
            else "not explained by typical weekly seasonality"
        )

        root_cause = (
            f"Unusual {trend_class} spike in {metric} on {dt}{seg_desc} ({seas_desc})"
        )

        explanation = (
            f"Analysis of '{metric}' on {dt} indicates an anomalous movement (z: {z_val}). "
            f"Regional breakdown demonstrates that {top_seg or 'the primary segment'} accounted for "
            f"{pct_contrib or 'a significant portion'}% of the net deviation. Weekly seasonality analysis "
            f"indicates that the observation is {seas_desc}. The trajectory was classified as '{trend_class}'."
        )

        # Action recommendation tailored to metric
        if "cancellation" in metric:
            recommended_action = (
                f"Review order fulfillment logs and inventory availability in region '{top_seg or 'affected regions'}' "
                "to investigate payment gateway rejects or merchant out-of-stock cancellations."
            )
        elif "delay" in metric:
            recommended_action = (
                f"Audit regional carrier transit times and logistics partner SLA compliance in state '{top_seg or 'affected regions'}'."
            )
        else:
            recommended_action = (
                f"Cross-reference marketing campaign records and promotional schedules in region '{top_seg or 'affected regions'}' "
                "to confirm event lift and evaluate inventory replenishment."
            )

        confidence = "high" if (top_seg and not is_seasonal and trend_class == "sudden") else "medium"

        return {
            "root_cause": root_cause[:200],
            "explanation": explanation,
            "confidence": confidence,
            "affected_segment": top_seg,
            "evidence_references": evidence_references,
            "recommended_action": recommended_action,
        }


class OpenAIProvider(BaseLLMProvider):
    """Provider connecting to OpenAI or any OpenAI-compatible API endpoint via httpx."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout_seconds: float = 45.0,
    ):
        self.provider_name = "openai"
        self.api_key = api_key or LLM_API_KEY
        self.model_name = model_name or LLM_MODEL
        self.base_url = (base_url or LLM_BASE_URL).rstrip("/")
        self.temperature = temperature if temperature is not None else LLM_TEMPERATURE
        self.timeout_seconds = timeout_seconds

        if not self.api_key:
            raise ValueError(
                "OpenAIProvider requires an API key. Set LLM_API_KEY in environment or .env."
            )

    def generate_conclusion(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        """Invoke chat completions endpoint using strict JSON output mode."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


class AnthropicProvider(BaseLLMProvider):
    """Provider connecting to Anthropic Claude Messages API via httpx."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 45.0,
    ):
        self.provider_name = "anthropic"
        self.api_key = api_key or LLM_API_KEY
        self.model_name = model_name or "claude-3-5-sonnet-20241022"
        self.timeout_seconds = timeout_seconds

        if not self.api_key:
            raise ValueError(
                "AnthropicProvider requires an API key. Set LLM_API_KEY in environment or .env."
            )

    def generate_conclusion(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        """Invoke Claude Messages API requesting structured JSON output."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": f"{user_prompt}\n\nRespond ONLY with a valid JSON object matching the schema."}
            ],
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        text_content = data["content"][0]["text"].strip()
        # Clean potential markdown fences
        if text_content.startswith("```"):
            text_content = re.sub(r"^```[a-zA-Z]*\n", "", text_content)
            text_content = re.sub(r"\n```$", "", text_content)
        return json.loads(text_content)


class GeminiProvider(BaseLLMProvider):
    """Provider connecting to Google Gemini REST API via httpx."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 45.0,
    ):
        self.provider_name = "gemini"
        self.api_key = api_key or LLM_API_KEY
        self.model_name = model_name or "gemini-1.5-flash"
        self.timeout_seconds = timeout_seconds

        if not self.api_key:
            raise ValueError(
                "GeminiProvider requires an API key. Set LLM_API_KEY in environment or .env."
            )

    def generate_conclusion(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        """Invoke Gemini generateContent with JSON response MIME type."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": LLM_TEMPERATURE,
            },
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        text_content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return json.loads(text_content)


def get_llm_provider(
    provider_name: Optional[str] = None,
    **kwargs: Any,
) -> BaseLLMProvider:
    """Factory function to instantiate the configured LLM provider.

    Args:
        provider_name: Optional override for provider ('mock', 'openai', 'anthropic', 'gemini').
                       Defaults to LLM_PROVIDER from configuration.
        **kwargs: Additional parameters forwarded to provider constructor.

    Returns:
        Configured BaseLLMProvider instance.
    """
    target = (provider_name or LLM_PROVIDER).lower().strip()

    if target == "mock":
        return MockLLMProvider(**kwargs)
    elif target in ("openai", "generic_openai"):
        return OpenAIProvider(**kwargs)
    elif target == "anthropic":
        return AnthropicProvider(**kwargs)
    elif target == "gemini":
        return GeminiProvider(**kwargs)
    else:
        raise ValueError(
            f"Unknown LLM provider '{target}'. Supported providers: 'mock', 'openai', 'anthropic', 'gemini'."
        )
