"""Tests for the LLM integration (mocked — no real API calls)."""

from unittest.mock import MagicMock, patch

import pytest

from ats_checker.checker import ATSReport, CheckResult
from ats_checker.llm import LLMResult, _build_user_prompt, get_llm_suggestions


@pytest.fixture()
def dummy_report() -> ATSReport:
    return ATSReport(
        overall_score=60,
        checks=[
            CheckResult("Contact", 10, 15, warnings=["No LinkedIn."]),
            CheckResult("Sections", 15, 20, suggestions=["Add Projects."]),
        ],
    )


class TestBuildPrompt:
    def test_contains_score(self, dummy_report: ATSReport):
        prompt = _build_user_prompt(dummy_report, "Some resume text")
        assert "60/100" in prompt

    def test_contains_warnings(self, dummy_report: ATSReport):
        prompt = _build_user_prompt(dummy_report, "Some resume text")
        assert "No LinkedIn." in prompt

    def test_truncates_resume(self, dummy_report: ATSReport):
        long_text = "x" * 5000
        prompt = _build_user_prompt(dummy_report, long_text)
        assert len(long_text[:3000]) <= len(prompt)
        assert "x" * 3001 not in prompt


class TestGetLLMSuggestions:
    def _mock_openai_response(self):
        choice = MagicMock()
        choice.message.content = "Improve your LinkedIn section."
        resp = MagicMock()
        resp.choices = [choice]
        return resp

    @patch("ats_checker.llm._call_openai")
    def test_explicit_openai(self, mock_call, dummy_report):
        mock_call.return_value = LLMResult("OpenAI", "gpt-4o-mini", "Do X, Y, Z.")
        result = get_llm_suggestions(dummy_report, "text", provider="openai")
        assert result.provider == "OpenAI"
        mock_call.assert_called_once()

    @patch("ats_checker.llm._call_anthropic")
    def test_explicit_anthropic(self, mock_call, dummy_report):
        mock_call.return_value = LLMResult("Anthropic", "claude-3-5-haiku", "Do A, B.")
        result = get_llm_suggestions(dummy_report, "text", provider="anthropic")
        assert result.provider == "Anthropic"
        mock_call.assert_called_once()

    @patch("ats_checker.llm._call_anthropic")
    @patch("ats_checker.llm._call_openai")
    def test_auto_falls_back(self, mock_openai, mock_anthropic, dummy_report):
        mock_openai.side_effect = RuntimeError("no key")
        mock_anthropic.return_value = LLMResult("Anthropic", "claude-3-5-haiku", "tips")
        result = get_llm_suggestions(dummy_report, "text", provider=None)
        assert result.provider == "Anthropic"

    @patch("ats_checker.llm._call_anthropic")
    @patch("ats_checker.llm._call_openai")
    def test_auto_raises_when_both_fail(self, mock_openai, mock_anthropic, dummy_report):
        mock_openai.side_effect = RuntimeError("no key")
        mock_anthropic.side_effect = RuntimeError("no key")
        with pytest.raises(RuntimeError, match="Neither openai nor anthropic"):
            get_llm_suggestions(dummy_report, "text", provider=None)
