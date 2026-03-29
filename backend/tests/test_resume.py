"""Tests for resume parsing: file text extraction + LLM structured parsing."""

import io
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFileParser:
    def test_extract_pdf(self, tmp_path):
        """Should extract text from PDF files."""
        from app.utils.file_parser import FileParser

        # Create a minimal PDF with pdfplumber-compatible content
        pdf_path = tmp_path / "test.pdf"

        with patch("app.utils.file_parser.pdfplumber") as mock_pdfplumber:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Python developer with 3 years experience"
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_pdfplumber.open.return_value = mock_pdf

            text = FileParser.extract_text(str(pdf_path), "resume.pdf")
            assert "Python developer" in text

    def test_extract_docx(self, tmp_path):
        """Should extract text from DOCX files."""
        from app.utils.file_parser import FileParser

        docx_path = tmp_path / "test.docx"

        with patch("app.utils.file_parser.Document") as MockDocument:
            mock_doc = MagicMock()
            mock_para1 = MagicMock()
            mock_para1.text = "Software Engineer"
            mock_para2 = MagicMock()
            mock_para2.text = "Skills: Python, Java"
            mock_doc.paragraphs = [mock_para1, mock_para2]
            MockDocument.return_value = mock_doc

            text = FileParser.extract_text(str(docx_path), "resume.docx")
            assert "Software Engineer" in text
            assert "Python" in text

    def test_unsupported_format_raises(self, tmp_path):
        """Unsupported file formats should raise FileFormatError."""
        from app.utils.file_parser import FileParser
        from app.exceptions import FileFormatError

        with pytest.raises(FileFormatError):
            FileParser.extract_text(str(tmp_path / "test.txt"), "resume.txt")

    def test_case_insensitive_extension(self, tmp_path):
        """File extension matching should be case-insensitive."""
        from app.utils.file_parser import FileParser

        pdf_path = tmp_path / "test.PDF"

        with patch("app.utils.file_parser.pdfplumber") as mock_pdfplumber:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Content"
            mock_pdf.pages = [mock_page]
            mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
            mock_pdf.__exit__ = MagicMock(return_value=False)
            mock_pdfplumber.open.return_value = mock_pdf

            text = FileParser.extract_text(str(pdf_path), "resume.PDF")
            assert text == "Content"


class TestResumeUploadValidation:
    def test_validate_file_size(self):
        """Files over max size should raise FileTooLargeError."""
        from app.exceptions import FileTooLargeError
        from app.utils.file_parser import validate_upload

        with pytest.raises(FileTooLargeError):
            validate_upload(
                filename="big.pdf",
                content_type="application/pdf",
                size=11 * 1024 * 1024,  # 11MB
                max_size_mb=10,
                allowed_types=["application/pdf"],
            )

    def test_validate_file_type(self):
        """Disallowed MIME types should raise FileFormatError."""
        from app.exceptions import FileFormatError
        from app.utils.file_parser import validate_upload

        with pytest.raises(FileFormatError):
            validate_upload(
                filename="image.png",
                content_type="image/png",
                size=1024,
                max_size_mb=10,
                allowed_types=["application/pdf"],
            )

    def test_validate_passes(self):
        """Valid file should pass without error."""
        from app.utils.file_parser import validate_upload

        validate_upload(
            filename="resume.pdf",
            content_type="application/pdf",
            size=1024 * 100,
            max_size_mb=10,
            allowed_types=["application/pdf"],
        )


class TestResumeService:
    async def test_upload_saves_and_parses(self, db, app_config, tmp_path):
        """Upload should save file, extract text, call LLM, and store in DB."""
        from app.services.resume_service import ResumeService

        # Create uploads dir
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        app_config.uploads.dir = str(upload_dir)

        mock_llm = AsyncMock()
        mock_llm.structured_parse = AsyncMock(
            return_value={
                "skills": ["Python", "FastAPI"],
                "experience_years": 2,
                "education": "本科 计算机科学",
            }
        )

        service = ResumeService(db=db, config=app_config, llm_client=mock_llm)

        # Simulate file upload
        file_content = b"fake pdf content"

        with patch("app.services.resume_service.FileParser") as MockParser:
            MockParser.extract_text.return_value = "Python developer, 2 years"

            result = await service.upload(
                file_content=file_content,
                filename="resume.pdf",
                content_type="application/pdf",
            )

        assert result["filename"] == "resume.pdf"
        assert result["parsed"]["skills"] == ["Python", "FastAPI"]
        assert result["parsed"]["experience_years"] == 2

        # Verify stored in DB
        row = await db.fetch_one("SELECT * FROM resume WHERE id = 1")
        assert row is not None
        assert row["filename"] == "resume.pdf"

    async def test_upload_replaces_and_cascades(self, db, app_config, tmp_path):
        """Re-uploading should overwrite resume and clear reports + messages."""
        from app.services.resume_service import ResumeService

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        app_config.uploads.dir = str(upload_dir)

        # Insert existing report and message
        await db.execute(
            "INSERT INTO reports (id, company_id, report_type, content, job_ids, preferences) "
            "VALUES ('r1', 'c1', 'match', 'old report', '[]', '{}')"
        )
        await db.execute(
            "INSERT INTO chat_messages (id, report_id, role, content) "
            "VALUES ('m1', 'r1', 'user', 'hello')"
        )

        mock_llm = AsyncMock()
        mock_llm.structured_parse = AsyncMock(
            return_value={"skills": [], "experience_years": None, "education": None}
        )

        service = ResumeService(db=db, config=app_config, llm_client=mock_llm)

        with patch("app.services.resume_service.FileParser") as MockParser:
            MockParser.extract_text.return_value = "New resume content"

            result = await service.upload(
                file_content=b"new pdf",
                filename="new_resume.pdf",
                content_type="application/pdf",
            )

        assert result["cleared"]["reports_deleted"] == 1

        # Verify cascade
        reports = await db.fetch_all("SELECT * FROM reports")
        assert len(reports) == 0
        messages = await db.fetch_all("SELECT * FROM chat_messages")
        assert len(messages) == 0

    async def test_get_resume(self, db, app_config):
        """Should return resume info or None."""
        from app.services.resume_service import ResumeService

        service = ResumeService(db=db, config=app_config, llm_client=AsyncMock())

        # No resume yet
        result = await service.get()
        assert result is None

        # Insert one
        await db.execute(
            "INSERT INTO resume (id, filename, file_path, parsed_data) "
            """VALUES (1, 'test.pdf', '/tmp/test.pdf', '{"skills":["Python"],"experience_years":1,"education":"BS"}')"""
        )
        result = await service.get()
        assert result["filename"] == "test.pdf"
        assert result["parsed"]["skills"] == ["Python"]

    async def test_delete_resume(self, db, app_config, tmp_path):
        """Should delete resume and cascade clear reports."""
        from app.services.resume_service import ResumeService

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        resume_file = upload_dir / "test.pdf"
        resume_file.write_bytes(b"content")
        app_config.uploads.dir = str(upload_dir)

        await db.execute(
            f"INSERT INTO resume (id, filename, file_path, parsed_data) "
            f"VALUES (1, 'test.pdf', '{resume_file}', '{{}}')"
        )

        service = ResumeService(db=db, config=app_config, llm_client=AsyncMock())
        result = await service.delete()
        assert "cleared" in result

        row = await db.fetch_one("SELECT * FROM resume WHERE id = 1")
        assert row is None
        assert not resume_file.exists()
