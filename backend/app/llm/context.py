"""LLM context window management."""

import tiktoken


class ContextManager:
    def __init__(self, encoding_name: str = "cl100k_base"):
        try:
            self._enc = tiktoken.get_encoding(encoding_name)
        except Exception:
            self._enc = None

    def truncate_history(
        self, messages: list[dict], max_rounds: int = 10
    ) -> list[dict]:
        """Keep the most recent N rounds of conversation.

        One round = one user message + one assistant message.
        """
        max_messages = max_rounds * 2
        if len(messages) <= max_messages:
            return messages
        return messages[-max_messages:]

    def build_chat_messages(
        self,
        system_message: dict,
        history: list[dict],
        new_message: str,
        max_rounds: int = 10,
    ) -> list[dict]:
        """Assemble the full message list for a chat completion call."""
        truncated = self.truncate_history(history, max_rounds=max_rounds)
        return [
            system_message,
            *truncated,
            {"role": "user", "content": new_message},
        ]

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count using tiktoken."""
        if self._enc is None:
            return len(text) // 4
        return len(self._enc.encode(text))
