"""Shared manager singletons for the crawl agent's tools.

The tool definitions themselves live in ``app/crawl/lc_tools.py`` as LangChain
tools. This module keeps the two stateful managers they operate on, so that a
single browser session and a single sandbox container are shared across every
tool call within a crawl.
"""

from .browser import BrowserManager
from .sandbox import SandboxManager

browser_mgr = BrowserManager()
sandbox_mgr = SandboxManager()

__all__ = ["browser_mgr", "sandbox_mgr"]
