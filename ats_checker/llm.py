"""LLM integration — thin wrapper over openai / anthropic SDKs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .checker import ATSReport

VALID_PROVIDERS = {"openai", "anthropic"}

_SENTENCE_END_RE = re.compile(r"[.!?]\s+")
MAX_RESUME_CHARS = 3000

SUPPLEMENT_PROMPT = (
    "You are an expert career coach and resume reviewer. "
    "Given an ATS compatibility report for a candidate's resume, "
    "provide 3-5 concise, actionable next steps the candidate should take "
    "to improve their resume. Be specific and practical. "
    "Do NOT repeat the scores — focus only on what to do next."
)

FULL_ANALYSIS_PROMPT = (
    "You are an expert career coach and ATS (Applicant Tracking System) specialist. "
    "Analyse the following resume for ATS compatibility. Provide:\n"
    "1. An overall ATS compatibility score out of 100.\n"
    "2. A brief critique covering: contact info, section structure, "
    "action verbs, quantifiable results, length, formatting, and skills/keywords.\n"
    "3. 3-5 specific, actionable steps to improve the resume.\n\n"
    "Be concise and practical. Use markdown formatting."
)


@dataclass
class LLMResult:
    provider: str
    model: str
    suggestions: str


def _truncate_at_sentence(text: str, limit: int = MAX_RESUME_CHARS) -> str:
    """Truncate *text* to at most *limit* chars, breaking at the last sentence boundary."""
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    match = None
    for match in _SENTENCE_END_RE.finditer(truncated):
        pass
    if match and match.end() > limit // 2:
        return truncated[: match.end()].rstrip()
    return truncated


def _build_supplement_prompt(report: ATSReport, resume_text: str) -> tuple[str, str]:
    """Build a prompt that supplements an existing rule-based report."""
    lines = [f"Overall ATS score: {report.overall_score}/100\n"]
    for check in report.checks:
        lines.append(f"## {check.name} [{check.score}/{check.max_score}]")
        for w in check.warnings:
            lines.append(f"  - Warning: {w}")
        for s in check.suggestions:
            lines.append(f"  - Suggestion: {s}")
    lines.append("\n--- Resume text (truncated) ---")
    lines.append(_truncate_at_sentence(resume_text))
    return SUPPLEMENT_PROMPT, "\n".join(lines)


def _build_full_analysis_prompt(resume_text: str) -> tuple[str, str]:
    """Build a prompt for full LLM-only analysis (no regex report)."""
    return FULL_ANALYSIS_PROMPT, _truncate_at_sentence(resume_text)


def _call_openai(system: str, user: str) -> LLMResult:
    from openai import OpenAI, OpenAIError

    model = "gpt-4o-mini"
    try:
        client = OpenAI()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=1024,
            temperature=0.7,
        )
    except OpenAIError:
        raise

    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI returned an empty response.")
    return LLMResult("OpenAI", model, content)


def _call_anthropic(system: str, user: str) -> LLMResult:
    from anthropic import Anthropic, APIError

    model = "claude-3-5-haiku-latest"
    try:
        client = Anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except APIError:
        raise

    if not resp.content:
        raise RuntimeError("Anthropic returned an empty response.")
    text = resp.content[0].text
    if not text:
        raise RuntimeError("Anthropic response contained no text content.")
    return LLMResult("Anthropic", model, text)


def _dispatch(system: str, user: str, provider: str | None) -> LLMResult:
    """Route to the correct provider, with auto-fallback when provider is None."""
    if provider == "openai":
        return _call_openai(system, user)
    if provider == "anthropic":
        return _call_anthropic(system, user)

    last_err: Exception | None = None
    for call_fn in (_call_openai, _call_anthropic):
        try:
            return call_fn(system, user)
        except (ImportError, RuntimeError, Exception) as exc:
            last_err = exc

    raise RuntimeError(
        "Neither openai nor anthropic SDK could connect. "
        "Install one (pip install openai / pip install anthropic) "
        f"and set the corresponding API key env var. Last error: {last_err}"
    )


def get_llm_suggestions(
    report: ATSReport,
    resume_text: str,
    provider: str | None = None,
) -> LLMResult:
    """Given an existing rule-based report, ask the LLM for next-step suggestions."""
    if provider is not None and provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Invalid provider '{provider}'. Choose from: {', '.join(sorted(VALID_PROVIDERS))}"
        )
    system, user = _build_supplement_prompt(report, resume_text)
    return _dispatch(system, user, provider)


def get_full_analysis(
    resume_text: str,
    provider: str | None = None,
) -> LLMResult:
    """Let the LLM do the full ATS analysis — no regex checks needed."""
    if provider is not None and provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Invalid provider '{provider}'. Choose from: {', '.join(sorted(VALID_PROVIDERS))}"
        )
    system, user = _build_full_analysis_prompt(resume_text)
    return _dispatch(system, user, provider)
