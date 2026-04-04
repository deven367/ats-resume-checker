# ATS Resume Checker

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
- LLM step is opt-in (`--llm` flag) and use SOTA LLMs (gpt-5.4 / claude-4-6-opus)
- LLM module uses official SDKs (`openai`, `anthropic`) — no raw HTTP calls
- Single `analyse_resume(text) -> ATSReport` function as the core API
- All checks return `CheckResult` with `passed`, `warnings`, and `suggestions`
- `typer` chosen for minimal CLI boilerplate; `rich` for colored terminal output

## Workflow conventions

- Update CLAUDE.md after every session with what was learnt
- New features and refactors always go through PRs (never commit directly to main)
- After every iteration, run and verify tests before pushing

## Development notes

- Workspace uses a venv created with uv Python 3.13 (`.venv/`)
- You are free to install dependencies in this `.venv`
- Once the `.venv` is activated, there is no need to activate it again.
- `pyproject.toml` declares the `ats-check` console script
- Uses `[dependency-groups]` (PEP 735) for test/anthropic deps — requires `uv`
- Run tests: `.venv/bin/python -m pytest tests/ -v` (or `uv run pytest tests/ -v`)
- CI runs on Python 3.10-3.12 via GitHub Actions with `uv`

## Session learnings

- `source .venv/bin/activate` may not work in sandboxed shells; use `.venv/bin/python` directly
- Summary, Projects, Certifications are optional resume sections — don't penalize if missing
- When `--llm` is used, regex checks are redundant — let the LLM do the full analysis
- `llm.py` has two modes: `get_llm_suggestions()` (supplement existing report) and `get_full_analysis()` (LLM-only, no regex)
- Always validate CLI flag inputs; `--llm` only accepts `openai`, `anthropic`, `auto`
- Preserve the LLM prompt helper contract: `_build_supplement_prompt()` returns `(system, user)`, and both LLM prompt paths should reuse the section-aware resume formatter so later sections survive truncation
- The frontend can expose provider/model dropdowns, but the backend should validate provider-model pairs and set the correct env var per provider (`OPENAI_API_KEY` vs `ANTHROPIC_API_KEY`)
- OpenAI model choices in the frontend should track current GPT-5.4 family docs, and Anthropic choices should track current Claude 4.6/4.5 docs rather than older GPT-4o or Claude 3.5/3.7-era defaults
- Current OpenAI Chat Completions calls for GPT-5.4-class models should use `max_completion_tokens`; `max_tokens` triggers a 400 unsupported-parameter error
- The current web frontend is FastHTML-based (`python-fasthtml`), using a GET home page, a small HTMX model-options route, and a multipart POST analyze route for file uploads
