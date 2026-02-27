"""Resume file parsing — supports PDF and DOCX."""

from pathlib import Path

import pdfplumber
from docx import Document


def extract_text(filepath: Path) -> str:
    suffix = filepath.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(filepath)
    if suffix in (".docx", ".doc"):
        return _extract_docx(filepath)
    raise ValueError(f"Unsupported file type: {suffix}. Use PDF or DOCX.")


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
