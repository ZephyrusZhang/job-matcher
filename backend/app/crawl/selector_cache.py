"""Selector learning and caching for the agent-driven crawler.

The cache records PagePatterns returned by the LLM agent.
When consecutive patterns are consistent (same selector + strategy),
the pattern is "locked" and subsequent pages skip the agent call.
"""

from pydantic import BaseModel


class PagePattern(BaseModel):
    """Result of a single LLM agent analysis of a listing page."""

    job_links: list[str] = []
    job_card_selector: str | None = None
    card_strategy: str = "href"  # "href" | "click"
    # Primary: "下一页" / ">" arrow button selector
    next_button_selector: str | None = None
    # Fallback: page number element selector (e.g. "li.number", "a.page-link")
    page_number_selector: str | None = None
    confidence: float = 0.0


class LockedPattern(BaseModel):
    """Stable pattern to use for all subsequent pages after locking."""

    job_card_selector: str
    card_strategy: str  # "href" | "click"
    next_button_selector: str | None = None
    page_number_selector: str | None = None


class SelectorCache:
    def __init__(self, lock_threshold: int = 1):
        self._threshold = lock_threshold
        self._locked: LockedPattern | None = None
        self._last_key: str | None = None
        self._streak: int = 0

    def _pattern_key(self, pattern: PagePattern) -> str:
        return f"{pattern.job_card_selector}|{pattern.card_strategy}"

    def record(self, pattern: PagePattern) -> None:
        """Record an agent result. Locks if streak reaches threshold."""
        if self._locked is not None:
            return

        key = self._pattern_key(pattern)
        if key == self._last_key:
            self._streak += 1
        else:
            self._last_key = key
            self._streak = 1

        if self._streak >= self._threshold:
            self._locked = LockedPattern(
                job_card_selector=pattern.job_card_selector,
                card_strategy=pattern.card_strategy,
                next_button_selector=pattern.next_button_selector,
                page_number_selector=pattern.page_number_selector,
            )

    def is_locked(self) -> bool:
        return self._locked is not None

    def get_locked(self) -> LockedPattern | None:
        return self._locked

    def force_lock(self, pattern: LockedPattern) -> None:
        self._locked = pattern

    def unlock(self) -> None:
        self._locked = None
        self._last_key = None
        self._streak = 0
