"""Tests for the LLM integration (mocked — no real API calls)."""

from unittest.mock import patch

import pytest

from ats_checker.checker import ATSReport, CheckResult
from ats_checker.llm import (
    LLMResult,
    _build_full_analysis_prompt,
    _build_supplement_prompt,
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

    def test_truncates_resume(self, dummy_report: ATSReport):
        long_text = "x" * 5000
        _, user = _build_supplement_prompt(dummy_report, long_text)
        assert "x" * 3000 in user
        assert "x" * 3001 not in user


class TestBuildFullAnalysisPrompt:
    def test_returns_system_and_user(self):
        system, user = _build_full_analysis_prompt("My resume text here.")
        assert "ATS" in system
        assert "My resume text here." in user

    def test_truncates_long_resume(self):
        long_text = "x" * 5000
        _, user = _build_full_analysis_prompt(long_text)
        assert len(user) <= 3000


class TestGetLLMSuggestions:
    @patch("ats_checker.llm._dispatch")
    def test_explicit_openai(self, mock_dispatch, dummy_report):
        mock_dispatch.return_value = LLMResult("OpenAI", "gpt-4o-mini", "Do X, Y, Z.")
        result = get_llm_suggestions(dummy_report, "text", provider="openai")
        assert result.provider == "OpenAI"
        mock_dispatch.assert_called_once()

    @patch("ats_checker.llm._dispatch")
    def test_explicit_anthropic(self, mock_dispatch, dummy_report):
        mock_dispatch.return_value = LLMResult("Anthropic", "claude-3-5-haiku-latest", "Do A, B.")
        result = get_llm_suggestions(dummy_report, "text", provider="anthropic")
        assert result.provider == "Anthropic"
        mock_dispatch.assert_called_once()

    def test_invalid_provider_raises(self, dummy_report):
        with pytest.raises(ValueError, match="Invalid provider"):
            get_llm_suggestions(dummy_report, "text", provider="invalid")


class TestGetFullAnalysis:
    @patch("ats_checker.llm._dispatch")
    def test_calls_dispatch(self, mock_dispatch):
        mock_dispatch.return_value = LLMResult("OpenAI", "gpt-4o-mini", "Full analysis.")
        result = get_full_analysis("resume text", provider="openai")
        assert result.suggestions == "Full analysis."
        mock_dispatch.assert_called_once()

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Invalid provider"):
            get_full_analysis("text", provider="bad")


class TestDispatch:
    @patch("ats_checker.llm._call_anthropic")
    @patch("ats_checker.llm._call_openai")
    def test_auto_falls_back(self, mock_openai, mock_anthropic):
        from ats_checker.llm import _dispatch

        mock_openai.side_effect = RuntimeError("no key")
        mock_anthropic.return_value = LLMResult("Anthropic", "claude-3-5-haiku-latest", "tips")
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
