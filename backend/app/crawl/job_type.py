"""Job type normalization: map various raw values to 实习 / 全职."""
import logging

logger = logging.getLogger(__name__)

# ── 2 个标准 job_type ──
STANDARD_JOB_TYPES = ["实习", "全职"]

# ── 关键词映射表：已知变体 → 标准 job_type ──
# key 全部小写，匹配时也转小写。优先做全匹配，再做子串匹配。
_KEYWORD_MAP: dict[str, str] = {
    # 实习
    "实习": "实习",
    "实习生": "实习",
    "实习岗": "实习",
    "日常实习": "实习",
    "暑期实习": "实习",
    "寒假实习": "实习",
    "春招实习": "实习",
    "秋招实习": "实习",
    "见习": "实习",
    "intern": "实习",
    "interns": "实习",
    "internship": "实习",
    "part-time intern": "实习",

    # 全职
    "全职": "全职",
    "正式": "全职",
    "正式员工": "全职",
    "校招": "全职",
    "社招": "全职",
    "校园招聘": "全职",
    "社会招聘": "全职",
    "应届": "全职",
    "应届生": "全职",
    "fulltime": "全职",
    "full-time": "全职",
    "full time": "全职",
    "regular": "全职",
}

# ── 标题/职责中出现即判定为实习的关键词 ──
_INTERN_TITLE_KEYWORDS: tuple[str, ...] = (
    "实习",
    "intern",
    "见习",
)


def _match_keyword(raw_lower: str) -> str | None:
    """Match a raw lowercase string against the keyword map.

    Tries exact match first, then falls back to substring match so values like
    '2026届暑期实习' or 'Software Engineer Intern' still get classified.
    """
    if raw_lower in _KEYWORD_MAP:
        return _KEYWORD_MAP[raw_lower]
    for kw, mapped in _KEYWORD_MAP.items():
        if kw in raw_lower:
            return mapped
    return None


def normalize_job_type(
    raw_job_type: str | None,
    title: str = "",
    responsibilities: str = "",
) -> str:
    """Normalize a raw job_type string to one of the 2 standard types.

    Strategy (parallels ``normalize_category``):
      1. Direct match in STANDARD_JOB_TYPES.
      2. Keyword map lookup (exact → substring).
      3. Title / responsibilities heuristic — if they mention 实习/intern, treat as 实习.
      4. Default to 全职 (the majority of crawled postings).

    No LLM call is made here: the binary classification space + tiny keyword
    set means rule-based matching is sufficient and cheap.

    Args:
        raw_job_type: Raw job_type value from the crawler (may be None / empty).
        title: Job title, used as fallback context.
        responsibilities: Job responsibilities, used as fallback context.

    Returns:
        Either "实习" or "全职". Never returns None — job_type is non-nullable
        in the normalized output.
    """
    # Step 1: direct match on raw value
    if raw_job_type and raw_job_type.strip() in STANDARD_JOB_TYPES:
        return raw_job_type.strip()

    # Step 2: keyword map on raw value
    if raw_job_type:
        raw_lower = raw_job_type.strip().lower()
        mapped = _match_keyword(raw_lower)
        if mapped:
            return mapped

    # Step 3: infer from title / responsibilities
    title_lower = (title or "").lower()
    for kw in _INTERN_TITLE_KEYWORDS:
        if kw in title_lower:
            return "实习"

    resp_lower = (responsibilities or "").lower()
    # Only the most unambiguous markers — avoid false positives from descriptions
    # that merely mention internships in passing.
    if "实习生" in resp_lower or "intern" in resp_lower[:200]:
        return "实习"

    # Step 4: default
    return "全职"
