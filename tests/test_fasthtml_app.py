"""Tests for the FastHTML frontend."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from bs4 import BeautifulSoup
from starlette.testclient import TestClient

from ats_checker.llm import LLMResult
from fasthtml_app import app

client = TestClient(app)


def test_model_options_switch_with_provider():
    response = client.get("/model-options", params={"provider": "anthropic"})

    assert response.status_code == 200
    assert "claude-sonnet-4-6" in response.text
    assert "gpt-5.4" not in response.text


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
    response = client.get("/model-options", params={"provider": "invalid"})
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
