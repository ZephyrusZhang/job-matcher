import json


class ContextManager:
    """Manages LLM context for chat conversations."""

    def build_chat_messages(
        self,
        system_message: dict,
        history: list[dict],
        new_message: str,
        max_rounds: int = 10,
    ) -> list[dict]:
        """
        Assemble messages for a chat call:
        1. System prompt with context
        2. Conversation history (sliding window)
        3. New user message
        """
        messages = [system_message]

        # Sliding window: keep last N rounds
        trimmed = self.truncate_history(history, max_rounds)
        for msg in trimmed:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": new_message})
        return messages

    def truncate_history(
        self, messages: list[dict], max_rounds: int = 10
    ) -> list[dict]:
        """Keep last N rounds (1 round = user + assistant)."""
        if not messages:
            return []
        # Count rounds from the end
        keep_count = max_rounds * 2
        if len(messages) <= keep_count:
            return messages
        return messages[-keep_count:]

    @staticmethod
    def format_jobs_for_context(jobs: list[dict]) -> str:
        """Format job list into a readable string for LLM context."""
        parts = []
        for i, job in enumerate(jobs, 1):
            requirements_must = job.get("requirements_must", "[]")
            if isinstance(requirements_must, str):
                try:
                    requirements_must = json.loads(requirements_must)
                except json.JSONDecodeError:
                    requirements_must = []

            parts.append(
                f"岗位 {i}: {job['title']}\n"
                f"  方向: {job['category']}\n"
                f"  地点: {job.get('location', '未知')}\n"
                f"  职责: {job.get('responsibilities', '未知')}\n"
                f"  必备技能: {', '.join(requirements_must) if requirements_must else '未知'}\n"
                f"  部门: {job.get('department', '未知')}\n"
                f"  产品: {job.get('department_product', '未知')}\n"
            )
        return "\n".join(parts)
