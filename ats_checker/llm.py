"""LLM integration — thin wrapper over openai / anthropic SDKs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .checker import ATSReport

SYSTEM_PROMPT = (
    "You are an expert career coach and resume reviewer. "
    "Given an ATS compatibility report for a candidate's resume, "
    "provide 3-5 concise, actionable next steps the candidate should take "
    "to improve their resume. Be specific and practical. "
    "Do NOT repeat the scores — focus only on what to do next."
)

VALID_PROVIDERS = {"openai", "anthropic"}

_SENTENCE_END_RE = re.compile(r"[.!?]\s+")
MAX_RESUME_CHARS = 3000


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


def _build_user_prompt(report: ATSReport, resume_text: str) -> str:
    lines = [f"Overall ATS score: {report.overall_score}/100\n"]
    for check in report.checks:
        lines.append(f"## {check.name} [{check.score}/{check.max_score}]")
        for w in check.warnings:
            lines.append(f"  - Warning: {w}")
        for s in check.suggestions:
            lines.append(f"  - Suggestion: {s}")
    lines.append("\n--- Resume text (truncated) ---")
    lines.append(_truncate_at_sentence(resume_text))
    return "\n".join(lines)


def _call_openai(prompt: str) -> LLMResult:
    from openai import OpenAI, OpenAIError

    model = "gpt-4o-mini"
    try:
        client = OpenAI()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
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


def _call_anthropic(prompt: str) -> LLMResult:
    from anthropic import Anthropic, APIError

    model = "claude-3-5-haiku-latest"
    try:
        client = Anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIError:
        raise

    if not resp.content:
        raise RuntimeError("Anthropic returned an empty response.")
    text = resp.content[0].text
    if not text:
        raise RuntimeError("Anthropic response contained no text content.")
    return LLMResult("Anthropic", model, text)


def get_llm_suggestions(
    report: ATSReport,
    resume_text: str,
    provider: str | None = None,
) -> LLMResult:
    """Call a cheap LLM for next-step suggestions.

    *provider*: ``"openai"``, ``"anthropic"``, or ``None`` (auto-detect
    by trying openai first, then anthropic).
    API keys are read from the standard env vars by each SDK.
    """
    if provider is not None and provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Invalid provider '{provider}'. Choose from: {', '.join(sorted(VALID_PROVIDERS))}"
        )

    prompt = _build_user_prompt(report, resume_text)

    if provider == "openai":
        return _call_openai(prompt)
    if provider == "anthropic":
        return _call_anthropic(prompt)

    # Auto: try openai, fall back to anthropic
    last_err: Exception | None = None
    for call_fn in (_call_openai, _call_anthropic):
        try:
            return call_fn(prompt)
        except (ImportError, RuntimeError, Exception) as exc:
            last_err = exc

    raise RuntimeError(
        "Neither openai nor anthropic SDK could connect. "
        "Install one (pip install openai / pip install anthropic) "
        f"and set the corresponding API key env var. Last error: {last_err}"
    )
