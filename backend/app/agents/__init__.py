"""Agent definitions.

This is where new agents go. Subclass ``BaseAgent``, declare the tools and
prompt, and register the instance below so it can be looked up by name::

    from app.core.langgraph import BaseAgent

    class ReviewAgent(BaseAgent):
        name = "review"
        tools = [some_tool]

        def build_system_prompt(self, **kwargs) -> str:
            return "You review job descriptions."

    review_agent = ReviewAgent()
    register(review_agent)

Everything else — checkpointing, memory, tracing, metrics, retries,
cancellation — is inherited from ``BaseAgent``.
"""

from app.core.langgraph import BaseAgent

_REGISTRY: dict[str, BaseAgent] = {}


def register(agent: BaseAgent) -> BaseAgent:
    """Register an agent instance under its name.

    Args:
        agent: The agent to register.

    Returns:
        The same agent, so this can wrap a constructor call.

    Raises:
        ValueError: When the name is already taken.
    """
    if agent.name in _REGISTRY:
        raise ValueError(f"agent '{agent.name}' is already registered")
    _REGISTRY[agent.name] = agent
    return agent


def get_agent(name: str) -> BaseAgent:
    """Look up a registered agent by name.

    Args:
        name: The agent name.

    Returns:
        The registered agent.

    Raises:
        KeyError: When no agent is registered under that name.
    """
    if name not in _REGISTRY:
        raise KeyError(f"unknown agent '{name}'. registered: {', '.join(sorted(_REGISTRY)) or 'none'}")
    return _REGISTRY[name]


def list_agents() -> list[str]:
    """Return every registered agent name."""
    return sorted(_REGISTRY)


from app.agents.crawler import crawler_agent  # noqa: E402
from app.agents.matcher import matcher_agent  # noqa: E402

register(crawler_agent)
register(matcher_agent)

__all__ = ["BaseAgent", "crawler_agent", "matcher_agent", "get_agent", "list_agents", "register"]
