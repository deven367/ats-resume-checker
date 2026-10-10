"""Helpers for a minimal web UI over the ATS checker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from .checker import ATSReport, analyse_resume
from .llm import LLMResult, _validate_provider_model, get_full_analysis
from .parser import extract_text

SUPPORTED_UPLOAD_SUFFIXES = {".pdf", ".doc", ".docx"}


@dataclass
class UploadedResumeAnalysis:
    resume_text: str
    report: ATSReport
    llm_result: LLMResult | None = None


def _validate_upload_name(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_SUFFIXES:
        raise ValueError("Only PDF and Word (.docx/.doc) files are supported.")
    return suffix


def _extract_uploaded_text(file_bytes: bytes, filename: str) -> str:
    suffix = _validate_upload_name(filename)

    with NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(file_bytes)
        temp_path = Path(handle.name)

    try:
        text = extract_text(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    if not text.strip():
        raise ValueError("Could not extract any text from the uploaded file.")

    return text


def analyse_resume_upload(
    file_bytes: bytes,
    filename: str,
    api_key: str | None = None,
    provider: str = "openai",
    model: str | None = None,
) -> UploadedResumeAnalysis:
    """Analyse an uploaded resume and optionally attach LLM feedback."""
    _validate_provider_model(provider, model)
    resume_text = _extract_uploaded_text(file_bytes, filename)
    report = analyse_resume(resume_text)

    normalized_key = (api_key or "").strip()
    llm_result = None
    if normalized_key:
        llm_result = get_full_analysis(
            resume_text,
            provider=provider,
            api_key=normalized_key,
            model=model,
        )

    return UploadedResumeAnalysis(
        resume_text=resume_text,
        report=report,
        llm_result=llm_result,
    )
