"""Extract ``:job[<uuid>]`` citations out of an assistant's final answer.

The match agent embeds job cards by writing ``:job[<id>]`` into the Markdown it
returns from ``final_answer``; the frontend replaces each marker with a card.
The same markers are the authoritative record of *which jobs a turn actually
recommended*, which is what ``match_messages.job_ids`` stores.

The regex is deliberately pinned to the UUID shape every row in ``jobs`` uses,
so a mis-transcribed id simply fails to match and degrades to plain text rather
than becoming a request that is guaranteed to 404.

Keep this in sync with ``frontend/src/lib/remarkJobEmbed.ts``. The frontend
walks the Markdown AST and therefore skips code automatically; working on the
raw string here, we have to strip fenced and inline code ourselves.
"""

import re

# Matches the frontend's JOB_RE.
_JOB_RE = re.compile(
    r":job\[\s*([0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})\s*\]"
)

# Fenced blocks first: a fence may legitimately contain backtick runs that
# would otherwise be mistaken for inline code.
_FENCED_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?(?:^[ \t]*\1[ \t]*$|\Z)", re.S | re.M)
_INLINE_CODE_RE = re.compile(r"(`+)(?:.|\n)*?\1")


def strip_code(markdown: str) -> str:
    """Blank out fenced and inline code spans, preserving surrounding text."""
    without_fences = _FENCED_RE.sub("", markdown)
    return _INLINE_CODE_RE.sub("", without_fences)


def extract_job_ids(markdown: str | None) -> list[str]:
    """Return cited job ids in order of first appearance.

    Args:
        markdown: An assistant answer, or ``None``.

    Returns:
        Lowercased job ids, deduplicated, code spans ignored.
    """
    if not markdown:
        return []

    seen: list[str] = []
    for match in _JOB_RE.finditer(strip_code(markdown)):
        job_id = match.group(1).lower()
        if job_id not in seen:
            seen.append(job_id)
    return seen
