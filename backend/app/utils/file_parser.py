"""File text extraction for PDF and DOCX."""

from pathlib import Path

import pdfplumber
from docx import Document

from app.exceptions import FileFormatError, FileTooLargeError


class FileParser:
    @staticmethod
    def extract_text(file_path: str, filename: str) -> str:
        """Extract plain text from PDF or DOCX file."""
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            return FileParser._extract_pdf(file_path)
        elif ext == ".docx":
            return FileParser._extract_docx(file_path)
        else:
            raise FileFormatError()

    @staticmethod
    def _extract_pdf(file_path: str) -> str:
        with pdfplumber.open(file_path) as pdf:
            texts = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
            return "\n".join(texts)

    @staticmethod
    def _extract_docx(file_path: str) -> str:
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def validate_upload(
    filename: str,
    content_type: str,
    size: int,
    max_size_mb: int,
    allowed_types: list[str],
) -> None:
    """Validate uploaded file size and type."""
    if size > max_size_mb * 1024 * 1024:
        raise FileTooLargeError()
    if content_type not in allowed_types:
        raise FileFormatError()
