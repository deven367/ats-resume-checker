"""Tests for resume file parsing."""

from pathlib import Path

import pytest

from ats_checker.parser import extract_text, split_resume_sections


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


def test_split_resume_sections_detects_common_headings(good_resume_text: str):
    sections = split_resume_sections(good_resume_text)
    names = [name for name, _ in sections]

    assert names[:2] == ["Header", "Professional Summary"]
    assert "Experience" in names
    assert "Education" in names
    assert "Skills" in names

    section_map = dict(sections)
    assert "John Doe" in section_map["Header"]
    assert "Led a team of 8 engineers" in section_map["Experience"]


def test_split_resume_sections_falls_back_to_single_block(bare_resume_text: str):
    sections = split_resume_sections(bare_resume_text)
    assert sections == [("Resume", bare_resume_text)]
