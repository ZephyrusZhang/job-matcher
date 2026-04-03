from pathlib import Path

from app.exceptions import FileFormatError


class FileParser:
    @staticmethod
    async def extract_text(file_path: str, filename: str) -> str:
        """Extract text from PDF or DOCX files."""
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            return _extract_pdf(file_path)
        elif ext == ".docx":
            return _extract_docx(file_path)
        else:
            raise FileFormatError()


def _extract_pdf(file_path: str) -> str:
    import pdfplumber

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n".join(text_parts)


def _extract_docx(file_path: str) -> str:
    from docx import Document

    doc = Document(file_path)
    return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
