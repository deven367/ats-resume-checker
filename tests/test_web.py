"""Tests for the web upload helper."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier

import httpx
import pytest
from docx import Document

from ats_checker.web import analyse_resume_upload


def test_analyse_resume_upload_without_api_key(sample_docx):
    result = analyse_resume_upload(sample_docx.read_bytes(), sample_docx.name)

    assert result.llm_result is None
    assert "jane@example.com" in result.resume_text


def test_invalid_upload_extension_raises():
    with pytest.raises(ValueError, match="Only PDF and Word"):
        analyse_resume_upload(b"hello", "resume.txt")


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("fail", [False, True])
def test_upload_credentials_stay_isolated_under_overlap(monkeypatch, provider, fail):
    import anthropic
    import openai

    monkeypatch.setenv("OPENAI_API_KEY", "shell-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "shell-anthropic-key")
    barrier = Barrier(2)
    observed = {}

    def respond(request):
        label = json.loads(request.content)["messages"][-1]["content"]
        header = "authorization" if provider == "openai" else "x-api-key"
        observed[label] = request.headers[header]
        barrier.wait(timeout=5)
        if provider == "openai":
            payload = {
                "id": "chatcmpl-test", "object": "chat.completion", "created": 1,
                "model": "gpt-5.4", "choices": [{"index": 0,
                    "message": {"role": "assistant", "content": "Feedback"},
                    "finish_reason": "length" if fail else "stop"}],
            }
        else:
            payload = {
                "id": "msg-test", "type": "message", "role": "assistant",
                "model": "claude-opus-4-6", "content": [{"type": "text", "text": "Feedback"}],
                "stop_reason": "max_tokens" if fail else "end_turn", "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        return httpx.Response(200, json=payload)

    module = openai if provider == "openai" else anthropic
    name = "OpenAI" if provider == "openai" else "Anthropic"
    original = getattr(module, name)

    def client(**kwargs):
        return original(
            **kwargs,
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        )

    monkeypatch.setattr(module, name, client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = []
        for label in ("first", "second"):
            document = Document()
            document.add_paragraph(label)
            data = BytesIO()
            document.save(data)
            pending.append(pool.submit(
                analyse_resume_upload, data.getvalue(), "resume.docx",
                api_key=f"{label}-key", provider=provider,
            ))
        for future in pending:
            if fail:
                with pytest.raises(RuntimeError, match="truncated"):
                    future.result(timeout=10)
            else:
                future.result(timeout=10)

    prefix = "Bearer " if provider == "openai" else ""
    assert observed == {"first": f"{prefix}first-key", "second": f"{prefix}second-key"}
    assert os.environ["OPENAI_API_KEY"] == "shell-openai-key"
    assert os.environ["ANTHROPIC_API_KEY"] == "shell-anthropic-key"


@pytest.mark.parametrize(
    "selection", [{"provider": "invalid"}, {"provider": "openai", "model": "claude-opus-4-6"}],
)
def test_selection_validation_precedes_extraction(selection):
    with pytest.raises(ValueError, match="Invalid"):
        analyse_resume_upload(b"not-a-docx", "resume.docx", **selection)
