"""Groq LLM client with retry logic and model fallback.

Wraps the Groq SDK to provide a clean interface for the agent layer.
Implements exponential backoff and automatic fallback to a smaller model
when the primary model is rate-limited.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from groq import Groq, APIError, RateLimitError

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around Groq with retry and fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = Groq(api_key=settings.groq_api_key)
        self._primary_model = settings.groq_model
        self._fallback_model = settings.groq_fallback_model
        self._max_retries = 3

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """Send a chat completion request with retry and fallback.

        Args:
            system_prompt: System-level instruction for the LLM.
            user_prompt: The user's actual prompt.
            temperature: Sampling temperature (0.0–1.0).
            max_tokens: Maximum tokens in the response.
            json_mode: If True, request JSON output format.

        Returns:
            The LLM's text response.

        Raises:
            RuntimeError: If all retries and fallback are exhausted.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Try primary model first, then fallback
        for model in [self._primary_model, self._fallback_model]:
            try:
                return self._call_with_retry(
                    model, messages, temperature, max_tokens, json_mode
                )
            except RateLimitError:
                logger.warning(
                    "Rate-limited on model '%s', falling back to '%s'.",
                    model,
                    self._fallback_model,
                )
                continue

        raise RuntimeError(
            "All LLM models exhausted after retries. Please try again later."
        )

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Generate and parse a JSON response from the LLM.

        Returns:
            Parsed JSON as a Python dict.

        Raises:
            ValueError: If the response is not valid JSON.
        """
        raw = self.generate(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        return self._parse_json(raw)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_with_retry(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        """Attempt the API call up to `_max_retries` times with backoff."""
        last_error: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}

                response = self._client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or ""
                logger.info(
                    "LLM call succeeded | model=%s | attempt=%d | tokens=%d",
                    model,
                    attempt,
                    response.usage.total_tokens if response.usage else 0,
                )
                return content

            except RateLimitError:
                raise  # Let the outer loop handle model fallback

            except APIError as exc:
                last_error = exc
                wait = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                logger.warning(
                    "API error on attempt %d/%d (model=%s): %s — retrying in %ds",
                    attempt,
                    self._max_retries,
                    model,
                    exc,
                    wait,
                )
                time.sleep(wait)

        raise RuntimeError(
            f"LLM call failed after {self._max_retries} retries: {last_error}"
        )

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        """Extract and parse JSON from LLM output, handling markdown fences."""
        text = raw.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM JSON output: %s", text[:200])
            raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
