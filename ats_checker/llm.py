"""LLM integration — thin wrapper over openai / anthropic SDKs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from .checker import ATSReport
from .parser import split_resume_sections

VALID_PROVIDERS = {"openai", "anthropic"}
DEFAULT_MODELS = {
    "openai": "gpt-5.4",
    "anthropic": "claude-opus-4-6",
}
MODEL_OPTIONS = {
    "openai": (
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-4.1",
    ),
    "anthropic": (
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
    ),
}

_SENTENCE_END_RE = re.compile(r"[.!?]\s+")
MAX_RESUME_CHARS = 50_000

SUPPLEMENT_PROMPT = (
    f"It is {datetime.now().strftime('%Y-%m-%d')} and you are an expert career coach and resume reviewer. "
    "Given an ATS compatibility report for a candidate's resume, "
    "provide 3-5 concise, actionable next steps the candidate should take "
    "to improve their resume. Be specific and practical. "
    "Do NOT repeat the scores — focus only on what to do next."
)

FULL_ANALYSIS_PROMPT = (
    f"It is {datetime.now().strftime('%Y-%m-%d')} and you are an expert career coach"
    "and ATS (Applicant Tracking System) specialist. "
    "Analyse the following resume for ATS compatibility. Provide:\n"
    "1. An overall ATS compatibility score out of 100.\n"
    "2. A brief critique covering: contact info, section structure, "
    "action verbs, quantifiable results, length, formatting, and skills/keywords.\n"
    "3. 3-5 specific, actionable steps to improve the resume.\n\n"
    "Be concise and practical. Use markdown formatting."
    "After the critique, return the resume in a more ATS-optimized version. "
    "Make sure to follow the same format as the original resume. "
    "The resume should be in the same language as the original resume. "
)


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

    formatted_size = sum(len(title) + 4 + len(content) for title, content in sections)
    formatted_size += 2 * (len(sections) - 1)
    if formatted_size <= limit:
        return "\n\n".join(f"## {title}\n{content}" for title, content in sections)

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
    """Build the user prompt payload for supplementing an existing rule-based report."""
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


def _build_supplement_prompt(report: ATSReport, resume_text: str) -> tuple[str, str]:
    """Build a prompt that supplements an existing rule-based report."""
    return SUPPLEMENT_PROMPT, _build_user_prompt(report, resume_text)


def _build_full_analysis_prompt(resume_text: str) -> tuple[str, str]:
    """Build a prompt for full LLM-only analysis (no regex report)."""
    return FULL_ANALYSIS_PROMPT, _format_resume_for_prompt(resume_text)


def _validate_provider_model(provider: str | None, model: str | None) -> None:
    if provider is not None and provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Invalid provider '{provider}'. Choose from: {', '.join(sorted(VALID_PROVIDERS))}"
        )

    if model is None:
        return

    if provider is None:
        raise ValueError("A model can only be selected when provider is set explicitly.")

    allowed_models = MODEL_OPTIONS[provider]
    if model not in allowed_models:
        allowed = ", ".join(allowed_models)
        raise ValueError(
            f"Invalid model '{model}' for provider '{provider}'. Choose from: {allowed}"
        )


def _call_openai(system: str, user: str, model: str, *, api_key: str | None = None) -> LLMResult:
    from openai import OpenAI

    with OpenAI(api_key=api_key) as client:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_completion_tokens=16384,
            temperature=0.7,
        )

    if not resp.choices:
        raise RuntimeError("OpenAI returned no choices.")
    choice = resp.choices[0]
    if choice.finish_reason == "length":
        raise RuntimeError("OpenAI response was truncated (token limit).")
    content = choice.message.content
    if not content or not content.strip():
        raise RuntimeError("OpenAI returned an empty response.")
    return LLMResult("OpenAI", model, content)


def _call_anthropic(system: str, user: str, model: str, *, api_key: str | None = None) -> LLMResult:
    from anthropic import Anthropic

    with Anthropic(api_key=api_key) as client:
        resp = client.messages.create(
            model=model,
            max_tokens=16384,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Anthropic response was truncated (token limit).")
    if not resp.content:
        raise RuntimeError("Anthropic returned an empty response.")
    text = "\n\n".join(block.text for block in resp.content if block.type == "text")
    if not text.strip():
        raise RuntimeError("Anthropic response contained no text content.")
    return LLMResult("Anthropic", model, text)


def _dispatch(
    system: str,
    user: str,
    provider: str | None,
    model: str | None = None,
    *,
    api_key: str | None = None,
) -> LLMResult:
    """Route to the correct provider, with auto-fallback when provider is None."""
    _validate_provider_model(provider, model)
    if api_key is not None and provider is None:
        raise ValueError("An API key requires an explicitly selected provider.")

    if provider == "openai":
        return _call_openai(system, user, model or DEFAULT_MODELS["openai"], api_key=api_key)
    if provider == "anthropic":
        return _call_anthropic(system, user, model or DEFAULT_MODELS["anthropic"], api_key=api_key)

    last_err: Exception | None = None
    for provider_name, call_fn in (
        ("openai", _call_openai),
        ("anthropic", _call_anthropic),
    ):
        try:
            return call_fn(system, user, DEFAULT_MODELS[provider_name])
        except Exception as exc:
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
    model: str | None = None,
    *,
    api_key: str | None = None,
) -> LLMResult:
    """Given an existing rule-based report, ask the LLM for next-step suggestions."""
    _validate_provider_model(provider, model)
    system, user = _build_supplement_prompt(report, resume_text)
    return _dispatch(system, user, provider, model=model, api_key=api_key)


def get_full_analysis(
    resume_text: str,
    provider: str | None = None,
    model: str | None = None,
    *,
    api_key: str | None = None,
) -> LLMResult:
    """Let the LLM do the full ATS analysis — no regex checks needed."""
    _validate_provider_model(provider, model)
    system, user = _build_full_analysis_prompt(resume_text)
    return _dispatch(system, user, provider, model=model, api_key=api_key)
