# ATS Resume Checker

A simple CLI tool that scores your resume for ATS (Applicant Tracking System) compatibility, gives actionable feedback, and optionally asks an LLM for personalized next steps.

## What it checks

| Check                | Weight | What it looks for                                   |
|----------------------|--------|-----------------------------------------------------|
| Contact Information  | 15     | Email, phone number, LinkedIn URL                   |
| Standard Sections    | 20     | Standalone Experience, Education, and Skills headings |
| Action Verbs         | 15     | Distinct, whole-word action verbs                   |
| Quantifiable Results | 15     | Achievement percentages, money, counts, and timings |
| Resume Length        | 10     | Word count (sweet spot: 300-800 words for 1 page)   |
| Formatting & ATS Tips| 15     | Bullet points, URLs, special characters             |
| Skills / Keywords    | 10     | Dedicated skills section with parseable keywords    |

Summary, Projects, and Certifications are optional. Section checks reuse the parser's
heading aliases; keyword-list credit is scoped to Skills content. Contact numbers,
dates, and numbers in links are not achievement metrics. Metric contexts are English.

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

To run the simple web UI:

```bash
uv sync --group web
```

## Usage

```bash
# Rule-based check only (no API key needed)
ats-check path/to/resume.pdf
ats-check path/to/resume.docx

# Add LLM-powered next steps (requires OPENAI_API_KEY or ANTHROPIC_API_KEY)
ats-check resume.pdf --llm auto          # auto-detect provider from env
ats-check resume.pdf --llm openai        # force OpenAI (default: gpt-5.4)
ats-check resume.pdf --llm anthropic     # force Anthropic (default: claude-opus-4-6)

# Run as a Python module
python -m ats_checker resume.pdf
```

DOCX extraction includes tables, section headers/footers, and native Word list markers.

LLM prompts preserve complete section content when it fits the input limit.
Token-limit responses raise an explicit error instead of presenting a partial analysis
as complete; Anthropic feedback includes every text block.

## Web UI

The repo now includes a minimal FastHTML frontend in `fasthtml_app.py`.

```bash
.venv/bin/python fasthtml_app.py
```

The UI lets a user:

- choose OpenAI or Anthropic
- paste the matching API key to load the models available to that account
- select a text-chat model returned by the provider's authenticated model-list endpoint
- upload a PDF or DOCX resume
- click **Analyze** for a full LLM ATS review and an optimized resume
- read Markdown feedback rendered server-side, with raw HTML and unsafe links disabled

Web API keys go directly to request-local SDK clients; the process environment is
unchanged. Parsing and provider calls run off the event loop. Python callers can pass
`api_key=` with an explicit provider; the CLI continues to use environment credentials.
Invalid provider/model selections and missing uploads return HTTP 400 with a safe retry
form. Selections are validated before resume extraction or provider calls.

The dropdown refreshes when the API key loses focus after a change or the provider
changes. HTMX sends credentials in the body of `POST /model-options`, never in a URL;
the server calls `client.models.list()` and follows SDK pagination. Missing keys,
failed requests, and empty catalogues leave no selectable model and show guidance
instead of falling back to a stale hardcoded list. Keys and catalogues are not cached.

OpenAI's model-list endpoint does not expose endpoint capabilities. The app uses a
name-based filter to exclude known audio, image, legacy-completion, and Responses-only
models from its text-chat dropdown. New GPT/ChatGPT/reasoning and Claude IDs do not need
to be added to an allowlist; the selected provider still enforces model availability.

Preferred models (selected only when returned for the supplied key):

- OpenAI: `gpt-5.4`
- Anthropic: `claude-opus-4-6`

## Deployment

GitHub Pages is **not** enough for this app as written. The current parser and analysis logic run in Python, and the OpenAI call should happen server-side.

Use one of these instead:

- Railway / Render / Fly.io / any Python host that can run a FastHTML app
- GitHub Pages only if you split the app into a static frontend plus a separate backend API

The web app does not serve local files. If static assets are added, mount a dedicated
asset directory with path-confined static serving; do not expose the working directory.

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

╭──── AI Next Steps (OpenAI / gpt-5.4) ────────╮
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
uv sync --locked --group test --group anthropic --group web
uv run pytest tests/ -v
```

Tests run in CI on Python 3.10, 3.11, and 3.12 via GitHub Actions.
Coverage is collected on every full run; CI fails below 80%. For a focused regression
run, use `--no-cov` so a single test module is not evaluated against the full-suite gate.
