"""Resume file parsing — supports PDF and DOCX."""

from __future__ import annotations

import re

from pathlib import Path

import pdfplumber
from docx import Document

_RAW_SECTION_HEADINGS: dict[str, tuple[str, ...]] = {
    "Professional Summary": (
        "summary",
        "objective",
        "profile",
        "about me",
        "professional summary",
    ),
    "Experience": (
        "experience",
        "work history",
        "employment",
        "professional experience",
    ),
    "Education": (
        "education",
        "academic",
        "qualifications",
        "degree",
    ),
    "Skills": (
        "skills",
        "technical skills",
        "core competencies",
        "proficiencies",
        "skills and tools",
    ),
    "Projects": (
        "projects",
        "personal projects",
        "key projects",
    ),
    "Certifications": (
        "certifications",
        "certificates",
        "licenses",
    ),
}
_SECTION_NORMALIZER_RE = re.compile(r"[^a-z0-9 ]+")


def _normalize_heading(line: str) -> str:
    normalized = line.strip().lower().replace("&", " and ").rstrip(":")
    normalized = _SECTION_NORMALIZER_RE.sub(" ", normalized)
    return " ".join(normalized.split())


SECTION_HEADINGS: dict[str, set[str]] = {
    title: {_normalize_heading(alias) for alias in aliases}
    for title, aliases in _RAW_SECTION_HEADINGS.items()
}


def extract_text(filepath: Path) -> str:
    suffix = filepath.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(filepath)
    if suffix in (".docx", ".doc"):
        return _extract_docx(filepath)
    raise ValueError(f"Unsupported file type: {suffix}. Use PDF or DOCX.")


def split_resume_sections(text: str) -> list[tuple[str, str]]:
    """Split resume text into labelled sections based on common heading lines."""
    lines = text.splitlines()
    if not lines:
        return []

    sections: list[tuple[str, str]] = []
    current_title = "Header"
    current_lines: list[str] = []
    found_heading = False

    def flush_section() -> None:
        content = "\n".join(current_lines).strip()
        if content:
            sections.append((current_title, content))

    for raw_line in lines:
        line = raw_line.strip()
        normalized = _normalize_heading(line)
        heading = next(
            (title for title, aliases in SECTION_HEADINGS.items() if normalized in aliases),
            None,
        )
        if heading:
            found_heading = True
            flush_section()
            current_title = heading
            current_lines = []
            continue

        if line:
            current_lines.append(line)
        elif current_lines and current_lines[-1]:
            current_lines.append("")

    flush_section()

    if not found_heading and text.strip():
        return [("Resume", text.strip())]

    return sections


def _extract_pdf(filepath: Path) -> str:
    pages: list[str] = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)


def _extract_docx(filepath: Path) -> str:
    doc = Document(str(filepath))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
