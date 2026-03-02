# ATS Resume Checker

A simple CLI tool that scores your resume for ATS (Applicant Tracking System) compatibility, gives actionable feedback, and optionally asks an LLM for personalized next steps.

## What it checks

| Check                | Weight | What it looks for                                   |
|----------------------|--------|-----------------------------------------------------|
| Contact Information  | 15     | Email, phone number, LinkedIn URL                   |
| Standard Sections    | 20     | Experience, Education, Skills, Summary, etc.        |
| Action Verbs         | 15     | Strong verbs at the start of bullet points          |
| Quantifiable Results | 15     | Numbers, percentages, dollar amounts                |
| Resume Length        | 10     | Word count (sweet spot: 300-800 words for 1 page)   |
| Formatting & ATS Tips| 15     | Bullet points, URLs, special characters             |
| Skills / Keywords    | 10     | Dedicated skills section with parseable keywords    |

## Installation

Requires Python 3.10+.

```bash
# With uv (recommended)
uv sync

# Or with pip
pip install -e .
```

To also install the Anthropic provider:

```bash
uv sync --group anthropic
```

## Usage

```bash
# Rule-based check only (no API key needed)
ats-check path/to/resume.pdf
ats-check path/to/resume.docx

# Add LLM-powered next steps (requires OPENAI_API_KEY or ANTHROPIC_API_KEY)
ats-check resume.pdf --llm auto          # auto-detect provider from env
ats-check resume.pdf --llm openai        # force OpenAI (gpt-4o-mini)
ats-check resume.pdf --llm anthropic     # force Anthropic (claude-3-5-haiku)

# Run as a Python module
python -m ats_checker resume.pdf
```

## Example output

```
╭──── ATS Score — resume.pdf ────╮
│          72 / 100              │
╰────────────────────────────────╯

  Contact Information  [10/15]
    ✓ Email address found.
    ✓ Phone number found.
    ✗ No LinkedIn profile link detected.
    → Add your LinkedIn profile URL (linkedin.com/in/yourname).

  ...

╭──── AI Next Steps (OpenAI / gpt-4o-mini) ────╮
│                                               │
│  1. Add a 'Projects' section showcasing ...   │
│  2. Expand bullet points with more detail ... │
│  3. Replace em-dashes with plain hyphens ...  │
│                                               │
╰───────────────────────────────────────────────╯
```

## Development

```bash
# Run tests
uv sync --group test
uv run pytest tests/ -v
```

Tests run in CI on Python 3.10, 3.11, and 3.12 via GitHub Actions.
