"""Message helpers for LangGraph agents.

Ported from the fastapi-langgraph-agent template.
"""

import tiktoken
from langchain_core.messages import BaseMessage
from langchain_core.messages import trim_messages as _trim_messages

from app.core.config import settings
from app.core.logging import logger
from app.schemas.agent import Message

try:
    _TIKTOKEN_ENCODING = tiktoken.encoding_for_model(settings.DEFAULT_LLM_MODEL)
except KeyError:
    _TIKTOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(messages: list) -> int:
    """Count tokens locally with tiktoken — no API call needed.

    Accepts both plain dicts and LangChain messages, so agents can size their
    own history without a round trip.
    """
    num_tokens = 0
    for message in messages:
        num_tokens += 4  # per-message role/name overhead
        if isinstance(message, dict):
            for _, value in message.items():
                if isinstance(value, str):
                    num_tokens += len(_TIKTOKEN_ENCODING.encode(value))
        elif isinstance(message, BaseMessage):
            content = message.content
            if isinstance(content, str):
                num_tokens += len(_TIKTOKEN_ENCODING.encode(content))
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, str):
                        num_tokens += len(_TIKTOKEN_ENCODING.encode(block))
                    elif isinstance(block, dict) and "text" in block:
                        num_tokens += len(_TIKTOKEN_ENCODING.encode(block["text"]))
    return num_tokens + 2  # reply priming


def dump_messages(messages: list[Message]) -> list[dict]:
    """Convert Message models to plain dicts."""
    return [message.model_dump() for message in messages]


def extract_text_content(content: str | list) -> str:
    """Extract plain text from an LLM content value.

    Handles both the simple string form and the structured block list returned
    by reasoning models: ``[{'type': 'reasoning', ...}, {'type': 'text', ...}]``.

    Args:
        content: Raw content from a LangChain message.

    Returns:
        Plain text, empty when nothing is extractable.
    """
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "reasoning":
                logger.debug("reasoning_block_received", reasoning_id=block.get("id"))
    return "".join(parts)


def process_llm_response(response: BaseMessage) -> BaseMessage:
    """Normalize a response so ``content`` is always a plain string."""
    if isinstance(response.content, list):
        response.content = extract_text_content(response.content)
    return response


def prepare_messages(messages: list[Message], system_prompt: str, max_tokens: int | None = None) -> list[Message]:
    """Trim history to the token budget and prepend the system prompt.

    Args:
        messages: The conversation so far.
        system_prompt: The system prompt to prepend.
        max_tokens: Token budget for history. Defaults to ``settings.MAX_TOKENS``.

    Returns:
        The system message followed by the trimmed history.
    """
    budget = max_tokens if max_tokens is not None else settings.MAX_TOKENS
    try:
        trimmed_messages = _trim_messages(
            dump_messages(messages),
            strategy="last",
            token_counter=count_tokens,
            max_tokens=budget,
            start_on="human",
            include_system=False,
            allow_partial=False,
        )
    except ValueError as e:
        if "Unrecognized content block type" in str(e):
            logger.warning("token_counting_failed_skipping_trim", error=str(e), message_count=len(messages))
            trimmed_messages = messages
        else:
            raise

    return [Message(role="system", content=system_prompt)] + trimmed_messages
