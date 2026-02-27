"""LLM integration — thin wrapper over openai / anthropic SDKs."""

from __future__ import annotations

from dataclasses import dataclass

from .checker import ATSReport

SYSTEM_PROMPT = (
    "You are an expert career coach and resume reviewer. "
    "Given an ATS compatibility report for a candidate's resume, "
    "provide 3-5 concise, actionable next steps the candidate should take "
    "to improve their resume. Be specific and practical. "
    "Do NOT repeat the scores — focus only on what to do next."
)


@dataclass
class LLMResult:
    provider: str
    model: str
    suggestions: str


def _build_user_prompt(report: ATSReport, resume_text: str) -> str:
    lines = [f"Overall ATS score: {report.overall_score}/100\n"]
    for check in report.checks:
        lines.append(f"## {check.name} [{check.score}/{check.max_score}]")
        for w in check.warnings:
            lines.append(f"  - Warning: {w}")
        for s in check.suggestions:
            lines.append(f"  - Suggestion: {s}")
    lines.append("\n--- Resume text (first 3000 chars) ---")
    lines.append(resume_text[:3000])
    return "\n".join(lines)


def _call_openai(prompt: str) -> LLMResult:
    from openai import OpenAI

    model = "gpt-4o-mini"
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
    return LLMResult("OpenAI", model, resp.choices[0].message.content)


def _call_anthropic(prompt: str) -> LLMResult:
    from anthropic import Anthropic

    model = "claude-3-5-haiku-latest"
    client = Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return LLMResult("Anthropic", model, resp.content[0].text)


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
    prompt = _build_user_prompt(report, resume_text)

    if provider == "openai":
        return _call_openai(prompt)
    if provider == "anthropic":
        return _call_anthropic(prompt)

    # Auto: try openai, fall back to anthropic
    try:
        return _call_openai(prompt)
    except Exception:
        pass
    try:
        return _call_anthropic(prompt)
    except Exception:
        pass

    raise RuntimeError(
        "Neither openai nor anthropic SDK could connect. "
        "Install one (pip install openai / pip install anthropic) "
        "and set the corresponding API key env var."
    )
