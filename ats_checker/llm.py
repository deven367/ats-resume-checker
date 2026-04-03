"""LLM integration — thin wrapper over openai / anthropic SDKs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .checker import ATSReport
from .parser import split_resume_sections

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
    """Truncate *text* to at most *limit* chars, preferring sentence or line boundaries."""
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    match = None
    for match in _SENTENCE_END_RE.finditer(truncated):
        pass
    if match and match.end() > limit // 2:
        return truncated[: match.end()].rstrip()
    newline = truncated.rfind("\n")
    if newline > limit // 2:
        return truncated[:newline].rstrip()
    return truncated.rstrip()


def _format_resume_for_prompt(resume_text: str, limit: int = MAX_RESUME_CHARS) -> str:
    """Build a compact section-aware resume excerpt for prompt input."""
    sections = [(title, content) for title, content in split_resume_sections(resume_text) if content]
    if len(sections) <= 1:
        return _truncate_at_sentence(resume_text, limit)

    parts: list[str] = []
    remaining = limit

    for idx, (title, content) in enumerate(sections):
        if remaining <= 0:
            break

        heading = f"## {title}\n"
        separator = "\n\n" if idx < len(sections) - 1 else ""
        if len(heading) > remaining:
            break

        parts.append(heading)
        remaining -= len(heading)

        available_for_content = max(0, remaining - len(separator))
        if available_for_content:
            sections_left = len(sections) - idx
            content_budget = available_for_content
            if sections_left > 1:
                content_budget = max(120, available_for_content // sections_left)
            content_budget = min(content_budget, available_for_content)
            snippet = _truncate_at_sentence(content, content_budget).rstrip()
            if snippet:
                parts.append(snippet)
                remaining -= len(snippet)

        if separator and remaining >= len(separator):
            parts.append(separator)
            remaining -= len(separator)

    formatted = "".join(parts).strip()
    return formatted or _truncate_at_sentence(resume_text, limit)


def _build_user_prompt(report: ATSReport, resume_text: str) -> str:
    lines = [f"Overall ATS score: {report.overall_score}/100\n"]
    for check in report.checks:
        lines.append(f"## {check.name} [{check.score}/{check.max_score}]")
        for w in check.warnings:
            lines.append(f"  - Warning: {w}")
        for s in check.suggestions:
            lines.append(f"  - Suggestion: {s}")
    lines.append("\n--- Resume text (section-aware, truncated) ---")
    lines.append(_format_resume_for_prompt(resume_text))
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
