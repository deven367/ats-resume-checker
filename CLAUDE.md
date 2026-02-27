# CLAUDE.md — ATS Resume Checker

## Project overview

Simple CLI tool that scores resumes for ATS (Applicant Tracking System) compatibility
and gives actionable feedback. Rule-based scoring with optional LLM-powered next-step suggestions.

## Tech stack

- **Python 3.10+** (venv at `.venv/`)
- `pdfplumber` — PDF text extraction
- `python-docx` — DOCX text extraction
- `typer` + `rich` — CLI framework and terminal output
- `openai` SDK — LLM suggestions via gpt-4o-mini (included)
- `anthropic` SDK — optional provider (`uv sync --group anthropic`)
- Installable via `uv sync` or `pip install -e .` (uses `pyproject.toml`)

## Project structure

```
ats_checker/
  __init__.py
  __main__.py      # python -m ats_checker entrypoint
  cli.py           # Typer CLI, rendering logic
  parser.py        # PDF/DOCX text extraction
  checker.py       # ATS scoring rules and report generation
  llm.py           # LLM suggestions (openai / anthropic SDKs)
```

## How to run

```bash
source .venv/bin/activate
ats-check path/to/resume.pdf                # rule-based check only
ats-check resume.docx --llm auto            # + LLM suggestions (auto-detect provider)
ats-check resume.docx --llm openai          # force OpenAI (gpt-4o-mini)
ats-check resume.docx --llm anthropic       # force Anthropic (claude-3-5-haiku)
python -m ats_checker resume.docx            # module invocation
```

## ATS checks (7 checks, 100 points total)

| Check                | Max | What it looks for                           |
|----------------------|-----|---------------------------------------------|
| Contact Information  | 15  | Email, phone, LinkedIn URL                  |
| Standard Sections    | 20  | Experience, Education, Skills, Summary, etc |
| Action Verbs         | 15  | Strong verbs in bullet points               |
| Quantifiable Results | 15  | Numbers, percentages, dollar amounts        |
| Resume Length        | 10  | Word count sweet spot (300-800 words)       |
| Formatting & ATS Tips| 15  | Bullet points, URLs, special characters     |
| Skills / Keywords    | 10  | Dedicated skills section, parseable keywords|

## Key design decisions

- Rule-based scoring is fast, offline, deterministic — runs without any API key
- LLM step is opt-in (`--llm` flag) and uses cheap models (gpt-4o-mini / claude-3-5-haiku)
- LLM module uses official SDKs (`openai`, `anthropic`) — no raw HTTP calls
- Single `analyse_resume(text) -> ATSReport` function as the core API
- All checks return `CheckResult` with `passed`, `warnings`, and `suggestions`
- `typer` chosen for minimal CLI boilerplate; `rich` for colored terminal output

## Development notes

- Workspace uses a venv created from miniforge Python 3.10 (`.venv/`)
- `pyproject.toml` declares the `ats-check` console script
- `requirements.txt` kept in sync for users who prefer `pip install -r`
- Uses `[dependency-groups]` (PEP 735) for test/anthropic deps — requires `uv`
- Run tests: `uv run pytest tests/ -v`
- CI runs on Python 3.10-3.12 via GitHub Actions with `uv`
