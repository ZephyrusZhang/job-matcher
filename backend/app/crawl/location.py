"""Location normalization: parse raw location strings into a list of city names.

Input examples (all observed in real crawler output):
    "深圳总部 / 北京 / 上海 / 广州"
    "上海, 北京"
    "北京、成都、广州、杭州、上海、深圳"
    "上海市，北京市"
    "北京市, 香港特别行政区, 上海市"
    "洛杉矶, 上海, 蒙特利尔"
    "中国香港"
    ""

Output: deduplicated list of city names preserving first-seen order, e.g.
    ["深圳", "北京", "上海", "广州"]
"""
import logging
import re

logger = logging.getLogger(__name__)

# Separators used in raw crawler output to delimit multiple cities.
# Note: full-width and half-width variants are both included.
_SEPARATOR_PATTERN = re.compile(r"[/、,，;；|\s]+")

# Suffixes to strip from city tokens. Applied repeatedly until no change,
# so "深圳总部市" would reduce to "深圳" (hypothetical edge case).
_STRIP_SUFFIXES: tuple[str, ...] = (
    "总部",
    "特别行政区",
    "市",  # 北京市 → 北京
    "省",
    "自治区",
)

# Direct alias map — applied AFTER suffix stripping.
# Keys must match the post-stripped form exactly.
_ALIAS_MAP: dict[str, str] = {
    "中国香港": "香港",
    "中国台湾": "台湾",
    "中国澳门": "澳门",
    "hongkong": "香港",
    "hong kong": "香港",
    "taipei": "台北",
    "tokyo": "东京",
    "singapore": "新加坡",
    "seoul": "首尔",
    "losangeles": "洛杉矶",
    "los angeles": "洛杉矶",
    "newyork": "纽约",
    "new york": "纽约",
    "seattle": "西雅图",
    "sanfrancisco": "旧金山",
    "san francisco": "旧金山",
    "siliconvalley": "硅谷",
    "silicon valley": "硅谷",
    "london": "伦敦",
    "paris": "巴黎",
    "montreal": "蒙特利尔",
    "istanbul": "伊斯坦布尔",
}

# Tokens that should be dropped entirely (not cities at all).
# Applied after suffix stripping.
_NOISE_TOKENS: frozenset[str] = frozenset({
    "",
    "总部",
    "中国",
    "海外",
    "remote",
    "其他",
    "all",
})

# Remove content inside parentheses, e.g. "上海(张江)" → "上海".
_PAREN_PATTERN = re.compile(r"[(（][^)）]*[)）]")


def _clean_token(token: str) -> str | None:
    """Clean a single token from the raw location string.

    Returns the canonical city name, or None if the token is noise.
    """
    # Strip parenthetical content and surrounding whitespace
    token = _PAREN_PATTERN.sub("", token).strip()
    if not token:
        return None

    # Lowercase for alias lookup
    lowered = token.lower()
    if lowered in _ALIAS_MAP:
        return _ALIAS_MAP[lowered]

    # Strip known suffixes repeatedly (order matters: longer first)
    changed = True
    while changed:
        changed = False
        for suffix in _STRIP_SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix):
                token = token[: -len(suffix)]
                changed = True

    # Alias lookup again after stripping
    lowered = token.lower()
    if lowered in _ALIAS_MAP:
        return _ALIAS_MAP[lowered]

    if lowered in _NOISE_TOKENS:
        return None

    return token or None


def normalize_location(raw_location: str | None) -> list[str]:
    """Normalize a raw location value into a deduplicated list of city names.

    Strategy:
      1. Split on common separators (/, 、, ,, ，, ;, ；, |, whitespace).
      2. Strip parenthetical content, known suffixes (总部/市/省/...), apply aliases.
      3. Drop noise tokens (empty, "中国", "remote", ...).
      4. Deduplicate preserving first-seen order.

    Args:
        raw_location: raw location value from the crawler, may be None/empty.

    Returns:
        A list of city names. Empty list if no valid cities can be extracted.
    """
    if not raw_location:
        return []

    if isinstance(raw_location, list):
        # Defensive: if the crawler already produced a list, normalize each entry.
        tokens: list[str] = []
        for item in raw_location:
            if isinstance(item, str):
                tokens.extend(_SEPARATOR_PATTERN.split(item))
    else:
        tokens = _SEPARATOR_PATTERN.split(raw_location)

    cities: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        cleaned = _clean_token(token)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            cities.append(cleaned)

    return cities
