"""OpenAI API client wrapper with streaming and retry support."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from openai import APITimeoutError, AsyncOpenAI, RateLimitError

from app.config import LLMConfig

logger = logging.getLogger(__name__)

_RETRYABLE_ERRORS = (APITimeoutError, RateLimitError)


class LLMClient:
    def __init__(self, config: LLMConfig, openai_client: AsyncOpenAI | None = None):
        self._client = openai_client or AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )
        self._model = config.model
        self._model_report = config.model_report
        self._max_tokens_report = config.max_tokens_report
        self._max_tokens_chat = config.max_tokens_chat
        self._temperature = config.temperature

    async def structured_parse(
        self,
        messages: list[dict],
        max_retries: int = 3,
    ) -> dict:
        """Non-streaming call that returns structured JSON.

        Used for: job parsing, resume parsing.
        """
        for attempt in range(max_retries):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.3,
                )
                return json.loads(response.choices[0].message.content)
            except _RETRYABLE_ERRORS:
                if attempt == max_retries - 1:
                    raise
                wait = 2**attempt
                logger.warning("LLM API error, retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)

    async def stream_generate(
        self,
        messages: list[dict],
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming call that yields text chunks.

        Used for: report generation, chat follow-up.
        """
        stream = await self._client.chat.completions.create(
            model=self._model_report,
            messages=messages,
            stream=True,
            temperature=self._temperature,
            max_tokens=max_tokens or self._max_tokens_report,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
