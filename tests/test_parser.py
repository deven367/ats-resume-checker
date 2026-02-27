"""Tests for resume file parsing."""

from pathlib import Path

import pytest

from ats_checker.parser import extract_text


def test_extract_docx(sample_docx: Path):
    text = extract_text(sample_docx)
    assert "Jane Doe" in text
    assert "jane@example.com" in text


def test_unsupported_format(tmp_path: Path):
    bad = tmp_path / "resume.txt"
    bad.write_text("hello")
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(bad)


def test_docx_suffix_case(sample_docx: Path):
    upper = sample_docx.parent / "RESUME.DOCX"
    sample_docx.rename(upper)
    text = extract_text(upper)
    assert "Jane Doe" in text
