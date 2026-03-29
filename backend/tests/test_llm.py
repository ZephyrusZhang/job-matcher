"""Tests for LLM client and related utilities."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


class TestLLMClient:
    @pytest.fixture
    def llm_config(self):
        from app.config import LLMConfig

        return LLMConfig(
            base_url="http://localhost:11434/v1",
            api_key="not-needed",
            model="test-model",
            model_report="test-model-report",
            max_tokens_report=4096,
            max_tokens_chat=2048,
            temperature=0.7,
        )

    @pytest.fixture
    def llm_client(self, llm_config):
        from app.llm.client import LLMClient

        mock_openai = MagicMock()
        mock_openai.chat = MagicMock()
        mock_openai.chat.completions = MagicMock()
        return LLMClient(llm_config, openai_client=mock_openai)

    async def test_structured_parse_returns_dict(self, llm_client):
        """structured_parse should return parsed JSON dict."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"skills": ["Python", "React"]}'

        with patch.object(
            llm_client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = await llm_client.structured_parse(
                messages=[{"role": "user", "content": "parse this"}]
            )
            assert result == {"skills": ["Python", "React"]}
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["model"] == "test-model"
            assert call_kwargs["response_format"] == {"type": "json_object"}

    async def test_stream_generate_yields_chunks(self, llm_client):
        """stream_generate should yield content chunks."""

        async def fake_stream():
            for text in ["Hello", " World", "!"]:
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = text
                yield chunk
            # Empty content chunk (should be skipped)
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = None
            yield chunk

        with patch.object(
            llm_client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = fake_stream()
            chunks = []
            async for c in llm_client.stream_generate(
                messages=[{"role": "user", "content": "hi"}]
            ):
                chunks.append(c)
            assert chunks == ["Hello", " World", "!"]
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["model"] == "test-model-report"
            assert call_kwargs["stream"] is True

    async def test_structured_parse_with_retries(self, llm_client):
        """Should retry on transient API errors."""
        from openai import APITimeoutError

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"result": "ok"}'

        with patch.object(
            llm_client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = [
                APITimeoutError(request=MagicMock()),
                mock_response,
            ]
            result = await llm_client.structured_parse(
                messages=[{"role": "user", "content": "test"}],
                max_retries=2,
            )
            assert result == {"result": "ok"}
            assert mock_create.call_count == 2

    async def test_structured_parse_exhausts_retries(self, llm_client):
        """Should raise after exhausting retries."""
        from openai import APITimeoutError

        with patch.object(
            llm_client._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = APITimeoutError(request=MagicMock())
            with pytest.raises(APITimeoutError):
                await llm_client.structured_parse(
                    messages=[{"role": "user", "content": "test"}],
                    max_retries=2,
                )
            assert mock_create.call_count == 2


class TestPromptTemplates:
    def test_parse_job_prompt(self):
        from app.llm.prompts.parse_job import build_parse_job_messages

        messages = build_parse_job_messages(
            raw_content="Some job text", company_name="测试公司"
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "结构化解析" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert "测试公司" in messages[1]["content"]
        assert "Some job text" in messages[1]["content"]

    def test_parse_resume_prompt(self):
        from app.llm.prompts.parse_resume import build_parse_resume_messages

        messages = build_parse_resume_messages(raw_text="Resume content here")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "简历解析" in messages[0]["content"]
        assert "Resume content here" in messages[1]["content"]

    def test_match_prompt(self):
        from app.llm.prompts.match import build_match_messages

        messages = build_match_messages(
            parsed_resume={"skills": ["Python"]},
            preferences={"interest": "后端"},
            favorited_jobs=[{"title": "Backend Dev"}],
        )
        assert len(messages) == 2
        assert "推荐" in messages[0]["content"]

    def test_compare_prompt(self):
        from app.llm.prompts.compare import build_compare_messages

        messages = build_compare_messages(
            parsed_resume={"skills": ["Python"]},
            preferences={"interest": "后端"},
            favorited_jobs=[{"title": "Job A"}, {"title": "Job B"}],
        )
        assert len(messages) == 2
        assert "对比" in messages[0]["content"]

    def test_chat_prompt(self):
        from app.llm.prompts.chat import build_chat_system_message

        msg = build_chat_system_message(
            parsed_resume={"skills": ["Python"]},
            preferences={"interest": "后端"},
            report_content="Report here",
            jobs_detail=[{"title": "Job A"}],
        )
        assert msg["role"] == "system"
        assert "咨询" in msg["content"]


class TestContextManager:
    def test_truncate_history_within_limit(self):
        from app.llm.context import ContextManager

        cm = ContextManager()
        history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        result = cm.truncate_history(history, max_rounds=5)
        assert len(result) == 2

    def test_truncate_history_over_limit(self):
        from app.llm.context import ContextManager

        cm = ContextManager()
        history = []
        for i in range(20):
            history.append({"role": "user", "content": f"q{i}"})
            history.append({"role": "assistant", "content": f"a{i}"})
        result = cm.truncate_history(history, max_rounds=3)
        # 3 rounds = 6 messages, should keep the last 6
        assert len(result) == 6
        assert result[0]["content"] == "q17"
        assert result[-1]["content"] == "a19"

    def test_estimate_tokens(self):
        from app.llm.context import ContextManager

        cm = ContextManager()
        tokens = cm.estimate_tokens("Hello world, this is a test.")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_build_chat_messages(self):
        from app.llm.context import ContextManager

        cm = ContextManager()
        messages = cm.build_chat_messages(
            system_message={"role": "system", "content": "You are helpful."},
            history=[
                {"role": "user", "content": "q1"},
                {"role": "assistant", "content": "a1"},
            ],
            new_message="What about q2?",
        )
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "q1"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "What about q2?"
