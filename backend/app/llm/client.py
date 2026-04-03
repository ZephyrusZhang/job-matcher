import json
import logging
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from app.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMClient:
    """Wraps OpenAI API for structured parsing and streaming generation."""

    def __init__(self, config: LLMConfig):
        self._config = config
        self._client: AsyncOpenAI | None = None
        self.model = config.model
        self.model_report = config.model_report
        self.config = config

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy initialization to avoid startup failures when API key is missing."""
        if self._client is None:
            kwargs: dict = {"api_key": self._config.api_key or "dummy"}
            if self._config.base_url:
                kwargs["base_url"] = self._config.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def structured_parse(self, messages: list[dict], schema: dict | None = None) -> dict:
        """Non-streaming call returning structured JSON."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return json.loads(content)

    async def stream_generate(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Streaming call yielding text chunks."""
        stream = await self.client.chat.completions.create(
            model=self.model_report,
            messages=messages,
            stream=True,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens_report,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def stream_chat(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Streaming call for chat responses."""
        stream = await self.client.chat.completions.create(
            model=self.model_report,
            messages=messages,
            stream=True,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens_chat,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
