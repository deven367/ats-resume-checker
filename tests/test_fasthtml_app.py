"""Tests for the FastHTML frontend."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import httpx
import pytest
from bs4 import BeautifulSoup
from starlette.testclient import TestClient

from ats_checker.llm import LLMResult
from fasthtml_app import app

client = TestClient(app)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_live_models_are_key_scoped_paginated_and_usable(provider, sample_docx, monkeypatch):
    import anthropic
    import openai

    prefix = "gpt" if provider == "openai" else "claude"
    first, second, other = (f"{prefix}-discovered-{suffix}" for suffix in ("a", "b", "c"))
    secret = "synthetic-secret-not-for-html"
    monkeypatch.setenv(
        "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY", "server-only-key",
    )

    def model_info(model):
        if provider == "openai":
            return {"id": model, "object": "model", "created": 1, "owned_by": "synthetic"}
        return {
            "id": model, "type": "model", "display_name": model,
            "created_at": "2026-01-01T00:00:00Z",
        }

    def respond(request):
        header = "authorization" if provider == "openai" else "x-api-key"
        key = request.headers[header].removeprefix("Bearer ")
        if key not in {"first-key", "second-key", "empty-key"}:
            return httpx.Response(401, json={"error": {
                "type": "authentication_error", "message": f"Incorrect API key: {key}",
            }})
        if request.url.path.endswith("/models"):
            if key == "empty-key":
                names = []
            elif key == "second-key":
                names = [other]
            elif provider == "anthropic":
                names = [second] if request.url.params.get("after_id") else [first]
            else:
                names = [
                    first, second, "whisper-1", "text-embedding-3-small",
                    "gpt-image-1", "gpt-audio", "gpt-5.4-pro", "gpt-5-codex", "o3-deep-research",
                ]
            return httpx.Response(200, json={
                "object": "list", "data": [model_info(name) for name in names],
                "has_more": provider == "anthropic" and key == "first-key" and names == [first],
                "first_id": names[0] if names else None,
                "last_id": names[-1] if names else None,
            })
        selected = json.loads(request.content)["model"]
        allowed = {first, second} if key == "first-key" else {other}
        if selected not in allowed:
            return httpx.Response(404, json={"error": {
                "type": "not_found_error", "message": "Model is not available to this key.",
            }})
        if provider == "openai":
            return httpx.Response(200, json={
                "id": "chatcmpl-test", "object": "chat.completion", "created": 1,
                "model": selected, "choices": [{"index": 0,
                    "message": {"role": "assistant", "content": "# Live feedback"},
                    "finish_reason": "stop"}],
            })
        return httpx.Response(200, json={
            "id": "msg-test", "type": "message", "role": "assistant", "model": selected,
            "content": [{"type": "text", "text": "# Live feedback"}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    module = openai if provider == "openai" else anthropic
    name = "OpenAI" if provider == "openai" else "Anthropic"
    original = getattr(module, name)
    monkeypatch.setattr(module, name, lambda **kwargs: original(
        **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    ))

    blank = client.post("/model-options", data={"provider": provider, "api_key": " "})
    blank_page = BeautifulSoup(blank.text, "html.parser")
    assert blank_page.select_one(".error") is None
    assert blank_page.select_one("#model option")["value"] == ""

    loaded = client.post(
        "/model-options", data={"provider": provider, "api_key": " first-key "},
    )
    page = BeautifulSoup(loaded.text, "html.parser")
    assert {option["value"] for option in page.select("#model option")} == {first, second}
    assert page.select_one("#model option[selected]")["value"] in {first, second}

    changed = client.post(
        "/model-options", data={"provider": provider, "api_key": "second-key", "model": first},
    )
    changed_page = BeautifulSoup(changed.text, "html.parser")
    assert {option["value"] for option in changed_page.select("#model option")} == {other}
    assert changed_page.select_one("#model option[selected]")["value"] == other

    for key in (secret, "empty-key"):
        failed = client.post("/model-options", data={"provider": provider, "api_key": key})
        failed_page = BeautifulSoup(failed.text, "html.parser")
        assert failed_page.select_one(".error") is not None
        assert {option["value"] for option in failed_page.select("#model option")} == {""}
        assert secret not in failed.text

    analyzed = client.post(
        "/analyze", data={"provider": provider, "api_key": "first-key", "model": second},
        files={"resume": (sample_docx.name, sample_docx.read_bytes())},
    )
    assert analyzed.status_code == 200
    panel = BeautifulSoup(analyzed.text, "html.parser").select_one(".llm-output")
    assert panel.h1.get_text() == "Live feedback"


def test_missing_upload_returns_a_retryable_client_error():
    response = client.post("/analyze", data={"provider": "openai"})
    page = BeautifulSoup(response.text, "html.parser")
    assert response.status_code == 400
    assert page.select_one(".error") is not None
    assert page.select_one('input[name="resume"]') is not None


def test_local_files_and_traversal_are_not_served(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "private.pdf").write_bytes(b"%PDF-synthetic-private-resume")
    (workspace / "private.txt").write_text("synthetic private report")
    (tmp_path / "outside.txt").write_text("synthetic outside marker")
    monkeypatch.chdir(workspace)

    for path in ("/private.pdf", "/private.txt", "/..%2foutside.txt"):
        response = client.get(path)
        assert response.status_code == 404


def test_feedback_renders_markdown_without_active_html(sample_docx, monkeypatch):
    feedback = (
        "# Feedback\n- Keep useful details.\n\n```python\nprint('safe')\n```\n"
        "<img src=x onerror=\"document.body.dataset.compromised='yes'\">\n"
        "<script>document.body.dataset.compromised='yes'</script>\n\n"
        "[Unsafe](javascript:alert(1))\n[Safe](https://example.com)"
    )
    monkeypatch.setattr(
        "ats_checker.web.get_full_analysis",
        lambda *args, **kwargs: LLMResult("OpenAI", "gpt-5.4", feedback),
    )
    response = client.post(
        "/analyze",
        data={"api_key": "synthetic-key"},
        files={"resume": (sample_docx.name, sample_docx.read_bytes())},
    )
    panel = BeautifulSoup(response.text, "html.parser").select_one(".llm-output")
    assert panel.find(["img", "script"]) is None
    assert panel.h1.get_text() == "Feedback"
    assert panel.li.get_text() == "Keep useful details."
    assert panel.code.get_text().strip() == "print('safe')"
    assert [link["href"] for link in panel.find_all("a")] == ["https://example.com"]


def test_other_requests_complete_while_analysis_waits(sample_docx, monkeypatch):
    entered, release = Event(), Event()

    def slow_provider(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return LLMResult("OpenAI", "gpt-5.4", "Feedback")

    monkeypatch.setattr("ats_checker.web.get_full_analysis", slow_provider)
    with TestClient(app) as concurrent_client, ThreadPoolExecutor(max_workers=2) as pool:
        upload = pool.submit(
            concurrent_client.post, "/analyze",
            data={"api_key": "synthetic-key"},
            files={"resume": (sample_docx.name, sample_docx.read_bytes())},
        )
        try:
            assert entered.wait(timeout=5)
            home = pool.submit(concurrent_client.get, "/")
            assert home.result(timeout=2).status_code == 200
            assert not release.is_set()
        finally:
            release.set()
        assert upload.result(timeout=5).status_code == 200


def test_invalid_model_options_provider_has_a_safe_error_page():
    response = client.post("/model-options", data={"provider": "invalid"})
    page = BeautifulSoup(response.text, "html.parser")
    assert response.status_code == 400
    assert page.select_one(".error") is not None
    assert page.select_one('#provider option[selected]')["value"] == "openai"


@pytest.mark.parametrize(
    "selection", [{"provider": "invalid"}, {"provider": "openai", "model": "claude-opus-4-6"}],
)
def test_invalid_analysis_selection_precedes_file_parsing(selection):
    response = client.post(
        "/analyze", data=selection, files={"resume": ("resume.docx", b"not-a-docx")},
    )
    page = BeautifulSoup(response.text, "html.parser")
    assert response.status_code == 400
    assert page.select_one(".error") is not None
    assert page.select_one('#provider option[selected]')["value"] == "openai"
