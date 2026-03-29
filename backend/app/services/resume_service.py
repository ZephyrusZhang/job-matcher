"""Resume upload, parsing, and management service."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import AppConfig
from app.database import Database
from app.llm.client import LLMClient
from app.llm.prompts.parse_resume import build_parse_resume_messages
from app.utils.file_parser import FileParser, validate_upload

logger = logging.getLogger(__name__)


class ResumeService:
    def __init__(self, db: Database, config: AppConfig, llm_client: LLMClient):
        self._db = db
        self._config = config
        self._llm = llm_client

    async def upload(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
    ) -> dict:
        """Upload, parse, and store resume. Cascades clear reports + messages."""
        validate_upload(
            filename=filename,
            content_type=content_type,
            size=len(file_content),
            max_size_mb=self._config.uploads.max_size_mb,
            allowed_types=self._config.uploads.allowed_types,
        )

        # Save file to disk
        upload_dir = Path(self._config.uploads.dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / filename
        file_path.write_bytes(file_content)

        # Extract text
        raw_text = FileParser.extract_text(str(file_path), filename)

        # LLM structured parsing
        messages = build_parse_resume_messages(raw_text)
        parsed = await self._llm.structured_parse(messages)
        parsed["raw_text"] = raw_text

        # Cascade clear: count before deleting
        reports_count = await self._db.fetch_one("SELECT COUNT(*) as cnt FROM reports")
        messages_count = await self._db.fetch_one("SELECT COUNT(*) as cnt FROM chat_messages")
        reports_deleted = reports_count["cnt"] if reports_count else 0
        messages_deleted = messages_count["cnt"] if messages_count else 0

        # Delete old reports (chat_messages cascade automatically)
        await self._db.execute("DELETE FROM reports")

        # Upsert resume (single row, id=1)
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT OR REPLACE INTO resume (id, filename, file_path, parsed_data, uploaded_at) "
            "VALUES (1, ?, ?, ?, ?)",
            (filename, str(file_path), json.dumps(parsed, ensure_ascii=False), now),
        )

        return {
            "filename": filename,
            "parsed": {
                "skills": parsed.get("skills", []),
                "experience_years": parsed.get("experience_years"),
                "education": parsed.get("education"),
                "raw_text": raw_text,
            },
            "uploaded_at": now,
            "cleared": {
                "reports_deleted": reports_deleted,
                "messages_deleted": messages_deleted,
            },
        }

    async def get(self) -> dict | None:
        """Get current resume info."""
        row = await self._db.fetch_one("SELECT * FROM resume WHERE id = 1")
        if row is None:
            return None

        parsed = json.loads(row["parsed_data"])
        return {
            "filename": row["filename"],
            "parsed": {
                "skills": parsed.get("skills", []),
                "experience_years": parsed.get("experience_years"),
                "education": parsed.get("education"),
                "raw_text": parsed.get("raw_text", ""),
            },
            "uploaded_at": row["uploaded_at"],
        }

    async def delete(self) -> dict:
        """Delete resume file and DB record, cascade clear reports."""
        row = await self._db.fetch_one("SELECT file_path FROM resume WHERE id = 1")

        reports_count = await self._db.fetch_one("SELECT COUNT(*) as cnt FROM reports")
        messages_count = await self._db.fetch_one("SELECT COUNT(*) as cnt FROM chat_messages")
        reports_deleted = reports_count["cnt"] if reports_count else 0
        messages_deleted = messages_count["cnt"] if messages_count else 0

        await self._db.execute("DELETE FROM reports")
        await self._db.execute("DELETE FROM resume WHERE id = 1")

        # Remove file from disk
        if row and row["file_path"]:
            path = Path(row["file_path"])
            if path.exists():
                path.unlink()

        return {
            "cleared": {
                "reports_deleted": reports_deleted,
                "messages_deleted": messages_deleted,
            }
        }
