"""Offline regression tests for provider error classification and redaction.

Locks in three fixes made after live verification against the NVIDIA Build API:

1. HTTP 410 / "end of life" is a PERMANENT error: it must not be retried.
2. Transient errors (429/5xx) still retry with bounded backoff.
3. ``_safe_error`` must not blow up with a TypeError when the original
   exception class requires keyword-only constructor arguments (the OpenAI
   SDK's ``APIStatusError`` needs ``response`` and ``body``); the original
   message and status code must survive redaction.

No network access and no real API keys are used.
"""

import pytest
from unittest.mock import AsyncMock

from app.core.model_provider import NVIDIABuildModelProvider


TEST_KEY = "nvapi-test-key-123"


class KeywordOnlyError(Exception):
    """Stand-in for SDK exceptions that cannot be rebuilt from a message."""

    def __init__(self, *, response, body):
        self.response = response
        self.body = body
        super().__init__("410 model reached end of life")


def _provider(max_retries: int = 2):
    return NVIDIABuildModelProvider(
        api_key=TEST_KEY,
        max_retries=max_retries,
        retry_delay_seconds=0,
    )


class TestPermanentErrorClassification:

    @pytest.mark.asyncio
    async def test_410_is_not_retried(self):
        """A model EOL (410) fails after exactly one attempt."""
        provider = _provider(max_retries=3)
        provider._client.chat.completions.create = AsyncMock(
            side_effect=Exception(
                "Error code: 410 - {'detail': \"The model has reached its end of life\"}"
            )
        )

        with pytest.raises(Exception) as exc_info:
            await provider.generate_response(prompt="hi", conversation_history=[])

        assert provider._client.chat.completions.create.await_count == 1
        assert "410" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_end_of_life_phrasing_is_not_retried(self):
        """The plain 'end of life' wording is also permanent."""
        provider = _provider(max_retries=3)
        provider._client.chat.completions.create = AsyncMock(
            side_effect=Exception("model reached end of life on 2026-08-26")
        )

        with pytest.raises(Exception):
            await provider.generate_response(prompt="hi", conversation_history=[])

        assert provider._client.chat.completions.create.await_count == 1

    @pytest.mark.asyncio
    async def test_401_is_not_retried(self):
        provider = _provider(max_retries=3)
        provider._client.chat.completions.create = AsyncMock(
            side_effect=Exception("Error code: 401 - unauthorized")
        )

        with pytest.raises(Exception):
            await provider.generate_response(prompt="hi", conversation_history=[])

        assert provider._client.chat.completions.create.await_count == 1

    @pytest.mark.asyncio
    async def test_429_is_retried_up_to_bound(self):
        """Rate limits are transient: bounded retries, then failure."""
        provider = _provider(max_retries=2)
        provider._client.chat.completions.create = AsyncMock(
            side_effect=Exception("Error code: 429 - rate limit exceeded")
        )

        with pytest.raises(Exception):
            await provider.generate_response(prompt="hi", conversation_history=[])

        assert provider._client.chat.completions.create.await_count == 3


class TestSafeErrorConstruction:

    def test_keyword_only_exception_falls_back_without_typeerror(self):
        """Rebuilding a keyword-only SDK exception must not raise TypeError."""
        provider = _provider()
        original = KeywordOnlyError(response=object(), body={})

        safe = provider._safe_error(original)

        assert isinstance(safe, Exception)
        assert "410" in str(safe)
        assert "end of life" in str(safe)

    def test_valueerror_semantics_preserved(self):
        provider = _provider()
        safe = provider._safe_error(ValueError("Empty response from nvidia_build"))

        assert isinstance(safe, ValueError)
        assert "Empty response" in str(safe)

    def test_api_key_redacted_from_raised_message(self):
        """Keys are stripped even without being registered on the instance."""
        provider = _provider()
        leaked = "boom: " + TEST_KEY

        safe = provider._safe_error(Exception(leaked))

        assert TEST_KEY not in str(safe)
        assert "[REDACTED]" in str(safe)
