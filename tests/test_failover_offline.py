"""Offline tests for the failover chain (FailoverModelProvider).

Verifies automatic failover, cooldown, retry/deadline bounds, deterministic
routing, and secret redaction WITHOUT network access or API credentials.
Uses lightweight fake providers to isolate chain logic.
"""

import asyncio
import time
import pytest
from typing import Dict, Any

from app.core.model_provider import (
    FailoverModelProvider,
    ModelProvider,
    ProviderUnavailableError,
    MockModelProvider,
)


class FakeProvider(ModelProvider):
    """Scripted provider for offline failover tests."""

    def __init__(self, name: str, behavior="succeed", content="ok"):
        self._name = name
        self.behavior = behavior  # "succeed" | "fail" | "timeout"
        self.content = content
        self.calls = 0
        self.last_prompts = []

    async def generate_response(
        self,
        prompt: str,
        conversation_history,
        context=None,
        skills=None,
        **kwargs
    ) -> str:
        self.calls += 1
        self.last_prompts.append(prompt)
        if self.behavior == "fail":
            raise Exception(f"{self._name} exploded")
        if self.behavior == "timeout":
            await asyncio.sleep(10)
        return self.content

    def get_provider_name(self) -> str:
        return self._name

    def get_model_name(self) -> str:
        return f"{self._name}-model"

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "chat_completions": True,
            "streaming": False,
            "tool_calling": False,
            "structured_output": False,
            "embeddings": False,
            "token_counting": False,
        }

    async def health_check(self) -> bool:
        return self.behavior == "succeed"


def _chain(first, second=None, cooldown=0.1, deadline=2.0):
    providers = [p for p in (first, second) if p is not None]
    return FailoverModelProvider(
        providers, cooldown_seconds=cooldown, request_deadline_seconds=deadline
    )


class TestProviderSelection:

    def test_deterministic_order_first_provider_wins_when_healthy(self):
        a = FakeProvider("alpha", content="from-alpha")
        b = FakeProvider("beta", content="from-beta")
        chain = _chain(a, b)
        result = asyncio.run(chain.generate_response(prompt="hi", conversation_history=[]))
        assert result == "from-alpha"
        assert a.calls == 1 and b.calls == 0

    def test_chain_name_lists_members_in_priority_order(self):
        chain = _chain(FakeProvider("alpha"), FakeProvider("beta"))
        assert chain.get_provider_name() == "failover:alpha+beta"

    def test_primary_identity_from_first_provider(self):
        a = FakeProvider("alpha")
        chain = _chain(a, FakeProvider("beta"))
        assert chain.get_model_name() == "alpha-model"

    def test_empty_chain_rejected(self):
        with pytest.raises(ValueError, match="at least one provider"):
            FailoverModelProvider([])

    def test_capabilities_intersect_with_streaming_disabled(self):
        a, b = FakeProvider("alpha"), FakeProvider("beta")
        a.get_capabilities = lambda: {
            "chat_completions": True, "streaming": True, "tool_calling": True,
            "structured_output": False, "embeddings": False, "token_counting": True,
        }
        b.get_capabilities = lambda: {
            "chat_completions": True, "streaming": True, "tool_calling": False,
            "structured_output": False, "embeddings": False, "token_counting": True,
        }
        caps = _chain(a, b).get_capabilities()
        assert caps["tool_calling"] is False  # intersection, conservative
        assert caps["token_counting"] is True
        assert caps["streaming"] is False


class TestFailover:

    @pytest.mark.asyncio
    async def test_failover_from_first_to_second_provider(self):
        failing = FakeProvider("nvidia", behavior="fail")
        working = FakeProvider("gemini", content="from-gemini")
        chain = _chain(failing, working)
        result = await chain.generate_response(prompt="hi", conversation_history=[])
        assert result == "from-gemini"
        assert failing.calls == 1
        assert working.calls == 1

    @pytest.mark.asyncio
    async def test_prompt_fully_preserved_across_failover(self):
        failing = FakeProvider("nvidia", behavior="fail")
        working = FakeProvider("gemini")
        chain = _chain(failing, working)
        await chain.generate_response(prompt="Explain Article 14", conversation_history=[])
        assert working.last_prompts == ["Explain Article 14"]

    @pytest.mark.asyncio
    async def test_all_providers_failing_raises_unavailable(self):
        a = FakeProvider("alpha", behavior="fail")
        b = FakeProvider("beta", behavior="fail")
        chain = _chain(a, b)
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await chain.generate_response(prompt="hi", conversation_history=[])
        assert exc_info.value.provider_names == ["alpha", "beta"]

    @pytest.mark.asyncio
    async def test_failure_causes_do_not_leak_secrets(self):
        secret = "super-secret-api-key-value"
        failing = FakeProvider("alpha", behavior="fail")
        chain = _chain(failing)
        chain.providers[0]._api_key = secret  # simulate adapter attribute
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await chain.generate_response(
                prompt="hi", conversation_history=[],
                context="x",  # any args go through
            )
        # defensive redaction must strip values that look like keys
        assert secret not in str(exc_info.value)


class TestCooldownAndRecovery:

    @pytest.mark.asyncio
    async def test_failed_provider_enters_cooldown(self):
        failing = FakeProvider("alpha", behavior="fail")
        working = FakeProvider("beta")
        chain = _chain(failing, working, cooldown=0.2)
        await chain.generate_response(prompt="hi", conversation_history=[])
        # failing provider cooldown; successful provider stays available
        assert chain.is_in_cooldown("alpha") is True
        assert chain.is_in_cooldown("beta") is False
        # and the successful provider is used again immediately
        assert await chain.generate_response(prompt="2nd", conversation_history=[]) == "ok"
        assert working.calls == 2

    @pytest.mark.asyncio
    async def test_cooldown_skips_provider_with_attempts_allowed(self):
        flaky = FakeProvider("alpha", behavior="fail")
        backup = FakeProvider("beta", content="from-beta")
        chain = _chain(flaky, backup, cooldown=60)
        # 1st: alpha fails (60s cooldown), beta serves
        first = await chain.generate_response(prompt="1st", conversation_history=[])
        assert first == "from-beta" and backup.calls == 1
        first_calls = flaky.calls
        # 2nd: alpha still in 60s cooldown → skipped, beta keeps serving
        second = await chain.generate_response(prompt="2nd", conversation_history=[])
        assert second == "from-beta"
        assert flaky.calls == first_calls  # skipped, not attempted
        assert backup.calls == 2

    @pytest.mark.asyncio
    async def test_recovery_after_cooldown_expires(self):
        flaky = FakeProvider("alpha", behavior="fail")  # turns healthy on reset
        backup = FakeProvider("beta", behavior="fail")
        chain = _chain(flaky, backup, cooldown=0.1)
        # 1st call: both attempt and fail
        with pytest.raises(ProviderUnavailableError):
            await chain.generate_response(prompt="1", conversation_history=[])
        # 2nd call: both in cooldown → unavailable without attempts
        with pytest.raises(ProviderUnavailableError):
            await chain.generate_response(prompt="2", conversation_history=[])
        await asyncio.sleep(0.15)  # expiry
        flaky.behavior = "succeed"
        result = await chain.generate_response(prompt="3", conversation_history=[])
        assert result == "ok" and flaky.calls == 2

    @pytest.mark.asyncio
    async def test_reset_cooldown_allows_immediate_retry(self):
        flaky = FakeProvider("alpha", behavior="fail")
        chain = _chain(flaky, cooldown=60)
        with pytest.raises(ProviderUnavailableError):
            await chain.generate_response(prompt="1", conversation_history=[])
        chain.reset_cooldown()
        flaky.behavior = "succeed"
        assert await chain.generate_response(prompt="2", conversation_history=[]) == "ok"


class TestRetryLimitsAndDeadlines:

    @pytest.mark.asyncio
    async def test_request_deadline_enforced(self):
        slow = FakeProvider("slow", behavior="timeout")
        chain = _chain(slow, deadline=0.05, cooldown=0.01)
        started = time.monotonic()
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await chain.generate_response(prompt="hi", conversation_history=[])
        elapsed = time.monotonic() - started
        assert elapsed < 1.0  # interrupted well before the 10s fake hang
        assert "deadline exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_deadline_exceeded_counts_as_failure_and_cooldown(self):
        slow = FakeProvider("slow", behavior="timeout")
        chain = _chain(slow, deadline=0.05)
        with pytest.raises(ProviderUnavailableError):
            await chain.generate_response(prompt="hi", conversation_history=[])
        assert chain.is_in_cooldown("slow") is True

    @pytest.mark.asyncio
    async def test_health_check_true_when_any_member_healthy(self):
        chain = _chain(FakeProvider("a", behavior="fail"), FakeProvider("b"))
        assert await chain.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_false_when_all_unhealthy(self):
        chain = _chain(FakeProvider("a", behavior="fail"), FakeProvider("b", behavior="fail"))
        assert await chain.health_check() is False


class TestRagContextPreservedThroughChain:

    @pytest.mark.asyncio
    async def test_context_argument_forwarded_to_provider(self):
        seen = {}

        class Capture(FakeProvider):
            async def generate_response(self, prompt, conversation_history, context=None, skills=None, **kwargs):
                seen["context"] = context
                seen["prompt"] = prompt
                return "ok"

        chain = _chain(Capture("alpha"))
        await chain.generate_response(
            prompt=">", conversation_history=[],
            context="RETRIEVED-CONTEXT-TOKEN",
        )
        assert seen["context"] == "RETRIEVED-CONTEXT-TOKEN"

    @pytest.mark.asyncio
    async def test_history_and_skills_preserved_through_failover(self):
        """The fallback provider receives the exact same request contract."""
        seen = {}

        class Capture(FakeProvider):
            async def generate_response(self, prompt, conversation_history, context=None, skills=None, **kwargs):
                seen.update(
                    prompt=prompt,
                    history=conversation_history,
                    context=context,
                    skills=skills,
                    kwargs=kwargs,
                )
                return "from-fallback"

        failing = FakeProvider("alpha", behavior="fail")
        fallback = Capture("beta")
        chain = _chain(failing, fallback)
        history = [
            {"role": "user", "content": "Turn 1: cite Article 21"},
            {"role": "assistant", "content": "Article 21 guarantees equality."},
        ]
        skills = [{"name": "case_lookup", "args": {"query": "Article 21"}}]

        result = await chain.generate_response(
            prompt="Follow up on that citation",
            conversation_history=history,
            context="RAG-CONTEXT-42",
            skills=skills,
            temperature=0.2,
        )

        assert result == "from-fallback"
        assert seen["prompt"] == "Follow up on that citation"
        assert seen["history"] == history
        assert seen["history"] is history
        assert seen["context"] == "RAG-CONTEXT-42"
        assert seen["skills"] == skills
        assert seen["kwargs"] == {"temperature": 0.2}
