"""Regression tests for redact(): generic credential-shape scrubbing.

Background: the failover chain only redacts _api_key attributes it knows;
an error message containing an unknown key-shape literal used to leak.
These tests lock in the shape-based redaction added to redact().

All literals below are synthetic, deliberately invalid placeholders
(contain "EXAMPLE"/"FAKE") — never real credentials.
"""

from app.core.model_provider import redact

NV_SAMPLE = "nvapi-EXAMPLEFAKEKEY0000000000000"
OPENAI_SAMPLE = "sk-EXAMPLEFAKEKEY000000000000000"
GOOGLE_SAMPLE = "AIzaEXAMPLEFAKEKEY00000000000000000"
GITHUB_SAMPLE = "ghp_EXAMPLEFAKEKEY00000000000000000"


def test_redacts_known_nvidia_key_shape():
    out = redact(f"provider error with {NV_SAMPLE} in the middle")
    assert NV_SAMPLE not in out
    assert "[REDACTED]" in out


def test_redacts_openai_google_and_github_key_shapes():
    assert "[REDACTED]" not in redact("normal message without keys")

    out = redact(
        f"x {OPENAI_SAMPLE} y | z {GOOGLE_SAMPLE} w | {GITHUB_SAMPLE} v"
    )
    for literal in (OPENAI_SAMPLE, GOOGLE_SAMPLE, GITHUB_SAMPLE):
        assert literal not in out
    assert out.count("[REDACTED]") >= 3


def test_redact_still_scrubs_exact_secrets_passed_by_caller():
    secret = "mycustomsecretvalue123"
    assert secret not in redact(f"error mentioning {secret}", secret)
