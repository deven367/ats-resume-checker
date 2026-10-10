"""Tests for the LLM integration (mocked — no real API calls)."""

from unittest.mock import patch

import httpx
import pytest

from ats_checker.checker import ATSReport, CheckResult
from ats_checker.llm import (
    LLMResult,
    _build_full_analysis_prompt,
    _build_supplement_prompt,
    _call_anthropic,
    _call_openai,
    _format_resume_for_prompt,
    _truncate_at_sentence,
    get_full_analysis,
    get_llm_suggestions,
)


@pytest.fixture()
def dummy_report() -> ATSReport:
    return ATSReport(
        overall_score=60,
        checks=[
            CheckResult("Contact", 10, 15, warnings=["No LinkedIn."]),
            CheckResult("Sections", 15, 20, suggestions=["Add Projects."]),
        ],
    )


class TestTruncateAtSentence:
    def test_short_text_unchanged(self):
        assert _truncate_at_sentence("Hello.", 100) == "Hello."

    def test_cuts_at_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence that is really long."
        result = _truncate_at_sentence(text, 40)
        assert result.endswith("Second sentence.")

    def test_never_exceeds_limit(self):
        text = "x" * 5000
        assert len(_truncate_at_sentence(text, 3000)) <= 3000


class TestBuildSupplementPrompt:
    def test_contains_score(self, dummy_report: ATSReport):
        _, user = _build_supplement_prompt(dummy_report, "Some resume text")
        assert "60/100" in user

    def test_contains_warnings(self, dummy_report: ATSReport):
        _, user = _build_supplement_prompt(dummy_report, "Some resume text")
        assert "No LinkedIn." in user

    def test_includes_full_resume_within_limit(self, dummy_report: ATSReport):
        long_text = "x" * 5000
        _, user = _build_supplement_prompt(dummy_report, long_text)
        assert "x" * 5000 in user


class TestBuildFullAnalysisPrompt:
    def test_passes_through_resume_within_limit(self):
        long_text = "x" * 5000
        _, user = _build_full_analysis_prompt(long_text)
        assert "x" * 5000 in user


class TestGetLLMSuggestions:
    def test_invalid_provider_raises(self, dummy_report):
        with pytest.raises(ValueError, match="Invalid provider"):
            get_llm_suggestions(dummy_report, "text", provider="invalid")

    def test_invalid_model_for_provider_raises(self, dummy_report):
        with pytest.raises(ValueError, match="Invalid model"):
            get_llm_suggestions(
                dummy_report,
                "text",
                provider="openai",
                model="claude-sonnet-4-6",
            )


class TestGetFullAnalysis:
    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Invalid provider"):
            get_full_analysis("text", provider="bad")

    def test_model_without_provider_raises(self):
        with pytest.raises(ValueError, match="provider is set explicitly"):
            get_full_analysis("text", model="gpt-5.4")


class TestDispatch:
    @patch("ats_checker.llm._call_anthropic")
    @patch("ats_checker.llm._call_openai")
    def test_auto_falls_back(self, mock_openai, mock_anthropic):
        from ats_checker.llm import _dispatch

        mock_openai.side_effect = RuntimeError("no key")
        mock_anthropic.return_value = LLMResult("Anthropic", "claude-sonnet-4-6", "tips")
        result = _dispatch("sys", "usr", provider=None)
        assert result.provider == "Anthropic"

    @patch("ats_checker.llm._call_anthropic")
    @patch("ats_checker.llm._call_openai")
    def test_raises_when_both_fail(self, mock_openai, mock_anthropic):
        from ats_checker.llm import _dispatch

        mock_openai.side_effect = RuntimeError("no key")
        mock_anthropic.side_effect = RuntimeError("no key")
        with pytest.raises(RuntimeError, match="Neither openai nor anthropic"):
            _dispatch("sys", "usr", provider=None)


@pytest.mark.parametrize(
    "choices,error",
    [
        ([{"index": 0, "message": {"role": "assistant", "content": "Partial resume"},
           "finish_reason": "length"}], "truncated"),
        ([{"index": 0, "message": {"role": "assistant", "content": None},
           "finish_reason": "stop"}], "empty"),
        ([], "no choices"),
    ],
)
def test_openai_rejects_incomplete_or_empty_responses(monkeypatch, choices, error):
    import openai

    payload = {
        "id": "chatcmpl-test", "object": "chat.completion", "created": 1,
        "model": "gpt-5.4", "choices": choices,
    }
    sdk = openai.OpenAI(
        api_key="synthetic-key",
        http_client=httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )),
    )
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: sdk)
    with pytest.raises(RuntimeError, match=error):
        _call_openai("system", "resume", "gpt-5.4")


@pytest.mark.parametrize(
    "stop_reason,blocks,error",
    [
        ("end_turn", [
            {"type": "thinking", "thinking": "internal", "signature": "synthetic"},
            {"type": "text", "text": "Critique."},
            {"type": "text", "text": "Rewritten resume."},
        ], None),
        ("max_tokens", [{"type": "text", "text": "Partial resume"}], "truncated"),
        ("end_turn", [], "empty"),
        ("end_turn", [{"type": "thinking", "thinking": "internal", "signature": "synthetic"}], "no text"),
    ],
)
def test_anthropic_response_completeness(monkeypatch, stop_reason, blocks, error):
    import anthropic

    payload = {
        "id": "msg-test", "type": "message", "role": "assistant",
        "model": "claude-opus-4-6", "content": blocks,
        "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    sdk = anthropic.Anthropic(
        api_key="synthetic-key",
        http_client=httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )),
    )
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: sdk)
    if error:
        with pytest.raises(RuntimeError, match=error):
            _call_anthropic("system", "resume", "claude-opus-4-6")
    else:
        result = _call_anthropic("system", "resume", "claude-opus-4-6")
        assert result.suggestions == "Critique.\n\nRewritten resume."


def test_sectioned_resume_within_limit_retains_experience_tail():
    resume = "Experience\n" + "Developed reliable APIs.\n" * 1500
    resume += "IMPORTANT_TAIL_FACT\nSkills\nPython, SQL"
    formatted = _format_resume_for_prompt(resume)
    assert "IMPORTANT_TAIL_FACT" in formatted
    assert "Python, SQL" in formatted


def test_oversized_resume_is_bounded_and_retains_later_sections():
    resume = "Experience\n" + "Developed reliable APIs.\n" * 1500
    resume += "Skills\nPython, SQL"
    formatted = _format_resume_for_prompt(resume, limit=300)
    assert len(formatted) <= 300
    assert "Python, SQL" in formatted


def test_explicit_key_requires_provider():
    with pytest.raises(ValueError, match="explicitly selected provider"):
        get_full_analysis("resume", api_key="synthetic-key")
