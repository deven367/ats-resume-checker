"""Resume file parsing — supports PDF and DOCX."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pdfplumber
from docx import Document
from docx.text.paragraph import Paragraph

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


def _docx_lines(container) -> Iterator[str]:
    for block in container.iter_inner_content():
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            properties = block._p.pPr
            numbering = properties.numPr if properties is not None else None
            style = block.style
            seen_styles = set()
            while numbering is None and style is not None and style.style_id not in seen_styles:
                seen_styles.add(style.style_id)
                properties = style.element.pPr
                numbering = properties.numPr if properties is not None else None
                style = style.base_style
            if numbering is not None and (numbering.numId is None or numbering.numId.val != 0):
                text = f"- {text}"
            yield text
        else:
            seen_cells = set()
            for row in block.rows:
                for cell in row.cells:
                    if cell._tc not in seen_cells:
                        seen_cells.add(cell._tc)
                        yield from _docx_lines(cell)


def _extract_docx(filepath: Path) -> str:
    doc = Document(str(filepath))
    lines = []
    for section in doc.sections:
        for header in (section.header, section.first_page_header, section.even_page_header):
            if not header.is_linked_to_previous:
                lines.extend(_docx_lines(header))
    lines.extend(_docx_lines(doc))
    for section in doc.sections:
        for footer in (section.footer, section.first_page_footer, section.even_page_footer):
            if not footer.is_linked_to_previous:
                lines.extend(_docx_lines(footer))
    return "\n".join(lines)
