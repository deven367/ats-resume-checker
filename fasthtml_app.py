"""Minimal FastHTML frontend for the ATS Resume Checker."""

from __future__ import annotations

from fasthtml.common import (
    H1,
    H2,
    Button,
    Card,
    Div,
    FastHTML,
    Fieldset,
    Form,
    HTTPException,
    Input,
    Label,
    Legend,
    Main,
    NotStr,
    Option,
    P,
    Section,
    Select,
    Small,
    Strong,
    Style,
    Title,
    picolink,
    serve,
)
from markdown_it import MarkdownIt
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from ats_checker.llm import (
    DEFAULT_MODELS,
    _validate_provider_model,
    get_available_models,
)
from ats_checker.web import UploadedResumeAnalysis, analyse_resume_upload


def _bad_request(req, exc):
    return _page(error=str(exc.detail))


app = FastHTML(hdrs=(picolink,), exception_handlers={400: _bad_request})
markdown = MarkdownIt("commonmark", {"html": False})

PAGE_STYLE = Style(
    """
    :root { --panel: #f6f7f9; --accent: #0f766e; --danger: #b42318; }
    main { max-width: 920px; margin: 0 auto; padding-bottom: 4rem; }
    .hero { padding: 2rem 0 1rem; }
    .hero p { max-width: 56rem; }
    .stack { display: grid; gap: 1rem; }
    .grid-two { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
    .muted { color: #475467; }
    .notice { padding: 1rem 1.25rem; border-left: 4px solid var(--accent); background: #ecfdf3; border-radius: 0.75rem; }
    .error { border-left-color: var(--danger); background: #fef3f2; color: var(--danger); }
    .llm-output { overflow-x: auto; background: var(--panel); color: #101828; padding: 1.5rem; border-radius: 1rem; line-height: 1.6; }
    .llm-output h1, .llm-output h2, .llm-output h3 { margin-top: 1.25rem; margin-bottom: 0.5rem; color: var(--accent); }
    .llm-output h1:first-child, .llm-output h2:first-child, .llm-output h3:first-child { margin-top: 0; }
    .llm-output ul, .llm-output ol { padding-left: 1.5rem; margin: 0.5rem 0; }
    .llm-output li { margin-bottom: 0.25rem; color: #101828; }
    .llm-output p { margin: 0.5rem 0; color: #101828; }
    .llm-output code { background: #e2e8f0; padding: 0.15rem 0.35rem; border-radius: 0.25rem; font-size: 0.9em; }
    .llm-output pre { background: #101828; color: #f8fafc; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; }
    .llm-output pre code { background: none; padding: 0; }
    """
)


def _model_select(
    provider: str,
    selected_model: str | None = None,
    models: list[str] | tuple[str, ...] = (),
    error: str | None = None,
) -> Div:
    if selected_model not in models:
        preferred = DEFAULT_MODELS[provider]
        selected_model = preferred if preferred in models else next(iter(models), None)
    return Div(
        Label(
            "Model",
            Select(
                *(
                    [
                        Option(name, value=name, selected=name == selected_model)
                        for name in models
                    ]
                    or [Option("Enter API key to load models", value="", selected=True)]
                ),
                name="model",
                id="model",
                required=True,
            ),
        ),
        _message_box(error, error=True) if error else None,
        id="model-field",
        aria_live="polite",
    )


def _analysis_form(provider: str = "openai", selected_model: str | None = None) -> Card:
    return Card(
        Form(
            Fieldset(
                Legend("Analyze a resume"),
                Div(
                    Label(
                        "Provider",
                        Select(
                            Option("OpenAI", value="openai", selected=provider == "openai"),
                            Option("Anthropic", value="anthropic", selected=provider == "anthropic"),
                            name="provider",
                            id="provider",
                            hx_post="/model-options",
                            hx_target="#model-field",
                            hx_swap="outerHTML",
                            hx_include="[name='provider'],[name='api_key'],[name='model']",
                            hx_sync="closest form:replace",
                        ),
                    ),
                    _model_select(provider, selected_model),
                    cls="grid-two",
                ),
                Div(
                    Label(
                        "API key",
                        Input(
                            type="password",
                            name="api_key",
                            placeholder="Paste the matching provider key",
                            required=True,
                            hx_post="/model-options",
                            hx_trigger="change",
                            hx_target="#model-field",
                            hx_swap="outerHTML",
                            hx_include="[name='provider'],[name='api_key'],[name='model']",
                            hx_sync="closest form:replace",
                        ),
                    ),
                    Label(
                        "Resume",
                        Input(type="file", name="resume", accept=".pdf,.doc,.docx", required=True),
                    ),
                    cls="grid-two",
                ),
                Small("Enter the matching API key to load available text models."),
                Button("Analyze", type="submit"),
            ),
            method="post",
            action="/analyze",
        )
    )


def _message_box(message: str, error: bool = False) -> Div:
    return Div(message, cls="notice error" if error else "notice")



def _result_panel(result: UploadedResumeAnalysis) -> Section:
    blocks = [H2("LLM Feedback")]

    if result.llm_result is None:
        blocks.append(
            _message_box(
                "No API key provided — an API key is required for LLM analysis.",
                error=True,
            )
        )
    else:
        blocks.extend(
            [
                P(
                    (
                        Strong("Provider: "),
                        f"{result.llm_result.provider} / {result.llm_result.model}",
                    )
                ),
                Div(NotStr(markdown.render(result.llm_result.suggestions)), cls="llm-output"),
            ]
        )

    return Section(*blocks, cls="stack")


def _page(
    provider: str = "openai",
    model: str | None = None,
    result: UploadedResumeAnalysis | None = None,
    error: str | None = None,
) -> tuple[Title, Style, Main]:
    sections = [
        Section(
            H1("ATS Resume Checker"),
            P(
                "Choose a provider and model, enter your API key, "
                "upload a resume, and get LLM-powered ATS feedback.",
            ),
            cls="hero",
        ),
        _analysis_form(provider=provider, selected_model=model),
    ]

    if error:
        sections.append(_message_box(error, error=True))
    if result is not None:
        sections.append(_result_panel(result))

    return Title("ATS Resume Checker"), PAGE_STYLE, Main(*sections)


@app.get("/")
def home():
    return _page()


@app.post("/model-options")
async def model_options(provider: str = "openai", api_key: str = "", model: str | None = None):
    try:
        _validate_provider_model(provider, None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not api_key.strip():
        return _model_select(provider)
    try:
        models = await run_in_threadpool(get_available_models, provider, api_key=api_key)
    except Exception:
        return _model_select(
            provider,
            error="Could not load models. Check the provider, API key, SDK installation, and connection.",
        )
    return _model_select(
        provider, model, models,
        error=None if models else "No compatible text models were returned for this API key.",
    )


@app.post("/analyze")
async def analyze(
    provider: str = "openai",
    model: str | None = None,
    api_key: str = "",
    resume: UploadFile | None = None,
):
    try:
        _validate_provider_model(provider, model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if resume is None or not resume.filename:
        raise HTTPException(status_code=400, detail="Upload a resume before running the analysis.")

    try:
        file_bytes = await resume.read()
        result = await run_in_threadpool(
            analyse_resume_upload,
            file_bytes,
            resume.filename,
            api_key=api_key,
            provider=provider,
            model=model,
        )
    except Exception as exc:
        return _page(provider=provider, model=model, error=f"Analysis failed: {exc}")

    return _page(provider=provider, model=model, result=result)


if __name__ == "__main__":
    serve()
