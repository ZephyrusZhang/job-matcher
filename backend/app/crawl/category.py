"""Category normalization: keyword mapping + LLM fallback with cache."""
import json
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 15 个标准类别 ──
STANDARD_CATEGORIES = [
    "算法", "后端", "客户端", "前端", "测试",
    "大数据", "安全", "硬件", "机器学习", "基础架构",
    "多媒体", "计算机视觉", "运维", "数据挖掘", "自然语言处理",
]

# ── 关键词映射表：已知变体 → 标准类别 ──
# key 全部小写，匹配时也转小写
_KEYWORD_MAP: dict[str, str] = {
    # 算法（含搜索/推荐/广告等算法子方向）
    "算法": "算法",
    "算法工程师": "算法",
    "算法研究员": "算法",
    "算法类": "算法",
    "推荐算法": "算法",
    "推荐算法工程师": "算法",
    "推荐": "算法",
    "搜索算法": "算法",
    "搜索算法工程师": "算法",
    "搜索": "算法",
    "策略算法": "算法",
    "策略": "算法",
    "风控算法": "算法",
    "风控": "算法",
    "aigc算法": "算法",
    "aigc": "算法",
    "广告算法": "算法",
    "广告算法工程师": "算法",

    # 后端
    "后端": "后端",
    "后端开发": "后端",
    "后端开发工程师": "后端",
    "基础后端": "后端",
    "服务端": "后端",
    "服务端开发": "后端",
    "java开发": "后端",
    "go开发": "后端",
    "python开发": "后端",
    "java": "后端",
    "golang": "后端",

    # 客户端
    "客户端": "客户端",
    "客户端开发": "客户端",
    "客户端开发工程师": "客户端",
    "android": "客户端",
    "android开发": "客户端",
    "ios": "客户端",
    "ios开发": "客户端",
    "桌面端开发": "客户端",
    "flutter": "客户端",
    "移动开发": "客户端",

    # 前端
    "前端": "前端",
    "前端开发": "前端",
    "前端开发工程师": "前端",
    "web开发": "前端",
    "web前端": "前端",

    # 测试
    "测试": "测试",
    "测试开发": "测试",
    "测试开发工程师": "测试",
    "qa": "测试",
    "质量保证": "测试",
    "自动化测试": "测试",
    "测试工程师": "测试",

    # 大数据
    "大数据": "大数据",
    "大数据开发": "大数据",
    "数据工程": "大数据",
    "数据引擎": "大数据",
    "数据仓库": "大数据",
    "spark": "大数据",

    # 安全
    "安全": "安全",
    "基础安全": "安全",
    "安全开发": "安全",
    "安全研发": "安全",
    "渗透测试": "安全",
    "端点防护": "安全",
    "网络安全": "安全",
    "安全工程师": "安全",

    # 硬件
    "硬件": "硬件",
    "硬件开发": "硬件",
    "嵌入式": "硬件",
    "嵌入式开发": "硬件",
    "固件": "硬件",
    "芯片": "硬件",
    "fpga": "硬件",

    # 机器学习
    "机器学习": "机器学习",
    "机器学习平台": "机器学习",
    "机器学习工程师": "机器学习",
    "机器学习算法工程师": "机器学习",
    "深度学习": "机器学习",
    "深度学习研究员": "机器学习",
    "深度学习算法工程师": "机器学习",
    "mlops": "机器学习",
    "大模型": "机器学习",
    "llm": "机器学习",
    "ai": "机器学习",

    # 基础架构
    "基础架构": "基础架构",
    "基础设施": "基础架构",
    "平台开发": "基础架构",
    "分布式系统": "基础架构",
    "云平台": "基础架构",
    "devops": "基础架构",
    "系统架构": "基础架构",
    "系统工程": "基础架构",
    "网络传输": "基础架构",
    "网络工程": "基础架构",

    # 多媒体
    "多媒体": "多媒体",
    "多媒体技术": "多媒体",
    "多媒体算法": "多媒体",
    "音视频": "多媒体",
    "音视频开发": "多媒体",
    "音视频算法工程师": "多媒体",
    "流媒体": "多媒体",
    "图形引擎": "多媒体",
    "图形图像渲染": "多媒体",
    "计算机图形学": "多媒体",
    "视频增强和处理": "多媒体",
    "视频编解码": "多媒体",
    "音频处理": "多媒体",
    "引擎": "多媒体",

    # 计算机视觉
    "计算机视觉": "计算机视觉",
    "计算机视觉算法工程师": "计算机视觉",
    "cv": "计算机视觉",
    "图像算法": "计算机视觉",
    "3d视觉": "计算机视觉",
    "内容理解": "计算机视觉",

    # 运维
    "运维": "运维",
    "运维开发工程师": "运维",
    "sre": "运维",
    "系统运维": "运维",
    "it运维": "运维",

    # 数据挖掘
    "数据挖掘": "数据挖掘",
    "数据挖掘算法工程师": "数据挖掘",
    "数据分析": "数据挖掘",
    "数据科学": "数据挖掘",
    "用户增长": "数据挖掘",

    # 自然语言处理
    "自然语言处理": "自然语言处理",
    "自然语言处理算法工程师": "自然语言处理",
    "nlp": "自然语言处理",
    "对话系统": "自然语言处理",
    "文本挖掘": "自然语言处理",
}

# ── 泛化 category 标记词 ──
# 包含这些词的 category 都被视为泛化（不同岗位可能映射到不同标准类别）
# 例：'技术类'、'技术类-软件'、'技术类-算法,硬件' 都因含 '技术' 而被识别
# 对这些 category，每次都用 title + responsibilities 调用 LLM，结果不缓存
_GENERIC_TOKENS: tuple[str, ...] = (
    "技术类",
    "技术 -",
    "技术-",
    "工程类",
    "研发类",
    "研发岗",
    "tech",
    "technology",
    "engineering",
    "r&d",
)


def _is_generic_category(raw_lower: str) -> bool:
    """Check if a category is too generic (depends on title for correct classification)."""
    # Exact matches for short generic words
    if raw_lower in {"技术", "工程", "研发", "rd", "tech"}:
        return True
    # Substring matches for compound forms like "技术类-软件"
    return any(token in raw_lower for token in _GENERIC_TOKENS)


# ── 运行时缓存（LLM 分类结果）──
_llm_cache: dict[str, str | None] = {}
_cache_lock = threading.Lock()

# 持久化缓存路径
_CACHE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "category_cache.json"


def _load_cache() -> None:
    """Load persisted LLM cache from disk."""
    global _llm_cache
    if _CACHE_FILE.exists():
        try:
            with open(_CACHE_FILE) as f:
                _llm_cache = json.load(f)
        except Exception:
            _llm_cache = {}


def _save_cache() -> None:
    """Persist LLM cache to disk."""
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump(_llm_cache, f, ensure_ascii=False, indent=2)


# Load on module import
_load_cache()


# Category classification uses a cheap chat model, NOT the reasoning model.
# Reasoning models (e.g. deepseek-reasoner) don't support response_format=json_object.
_CLASSIFY_MODEL = "deepseek-chat"
_CLASSIFY_MAX_RETRIES = 3


def _llm_classify(raw_category: str, title: str = "", responsibilities: str = "") -> str | None:
    """Use LLM to classify a job into a standard category.

    Sends category + title + responsibilities as context so the LLM can
    classify even when category is an opaque code (e.g. "j1007").

    Returns:
        Standard category name if classified successfully.
        None if LLM determines it's a non-tech category.

    Raises:
        RuntimeError if LLM API call fails after retries.
    """
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY environment variable not set")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    )

    categories_str = "、".join(STANDARD_CATEGORIES)

    # Build user message with all available context
    parts = [f"category: {raw_category}"]
    if title:
        parts.append(f"title: {title}")
    if responsibilities:
        parts.append(f"responsibilities: {responsibilities[:300]}")
    user_content = "\n".join(parts)

    last_error = None
    for attempt in range(1, _CLASSIFY_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=_CLASSIFY_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"你是一个技术岗位分类器。根据提供的岗位信息，将其归类到以下标准类别之一：\n"
                            f"{categories_str}\n\n"
                            f"注意：category 字段可能是内部代码（如 j1007、10001），此时请根据 title 和 responsibilities 来判断。\n"
                            f"如果是非技术岗位（如产品、设计、运营、市场、销售），返回 null。\n"
                            f"只返回 JSON：{{\"category\": \"标准类别名\"}} 或 {{\"category\": null}}"
                        ),
                    },
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=50,
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("LLM returned empty content")
            result = json.loads(content)
            mapped = result.get("category")
            if mapped and mapped in STANDARD_CATEGORIES:
                return mapped
            return None
        except Exception as e:
            last_error = e
            logger.warning(
                f"LLM classify attempt {attempt}/{_CLASSIFY_MAX_RETRIES} "
                f"failed for '{raw_category}': {e}"
            )

    raise RuntimeError(
        f"LLM classification failed after {_CLASSIFY_MAX_RETRIES} retries "
        f"for '{raw_category}': {last_error}"
    )


def _llm_classify_batch(items: list[dict]) -> list[str | None]:
    """Classify multiple jobs in a single LLM call.

    Args:
        items: list of dicts with keys: raw_category, title, responsibilities.

    Returns:
        list of standard category names (or None for non-tech), same order as input.

    Raises:
        RuntimeError if LLM API call fails after retries.
    """
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY environment variable not set")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    )

    categories_str = "、".join(STANDARD_CATEGORIES)

    # Build numbered user message
    lines = []
    for i, item in enumerate(items):
        parts = [f"category={item['raw_category']!r}"]
        if item.get("title"):
            parts.append(f"title={item['title']!r}")
        if item.get("responsibilities"):
            parts.append(f"responsibilities={item['responsibilities'][:200]!r}")
        lines.append(f"[{i}] " + " | ".join(parts))
    user_content = "\n".join(lines)

    last_error = None
    for attempt in range(1, _CLASSIFY_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=_CLASSIFY_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"你是一个技术岗位分类器。下面给你 {len(items)} 个岗位，"
                            f"请把每一个分类到以下标准类别之一：\n"
                            f"{categories_str}\n\n"
                            f"注意：category 字段可能是内部代码或泛词（如 j1007、技术类-软件），"
                            f"此时请根据 title 和 responsibilities 来判断。\n"
                            f"如果是非技术岗位（产品、设计、运营、市场、销售等），category 设为 null。\n"
                            f"严格只返回 JSON："
                            f'{{"results": [{{"index": 0, "category": "标准类别名"}}, ...]}}\n'
                            f"results 数组的长度必须等于输入的岗位数量，index 从 0 开始递增。"
                        ),
                    },
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=64 + 30 * len(items),
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("LLM returned empty content")
            payload = json.loads(content)
            results_raw = payload.get("results", [])
            if not isinstance(results_raw, list):
                raise ValueError(f"Invalid response shape: {payload}")

            # Map results by index, default None for missing
            by_index: dict[int, str | None] = {}
            for r in results_raw:
                if not isinstance(r, dict):
                    continue
                idx = r.get("index")
                cat = r.get("category")
                if not isinstance(idx, int):
                    continue
                if cat and cat in STANDARD_CATEGORIES:
                    by_index[idx] = cat
                else:
                    by_index[idx] = None

            return [by_index.get(i) for i in range(len(items))]
        except Exception as e:
            last_error = e
            logger.warning(
                f"LLM batch classify attempt {attempt}/{_CLASSIFY_MAX_RETRIES} "
                f"failed ({len(items)} items): {e}"
            )

    raise RuntimeError(
        f"LLM batch classification failed after {_CLASSIFY_MAX_RETRIES} retries: {last_error}"
    )


def prebatch_classify(
    raw_jobs: list[dict],
    batch_size: int = 32,
    progress_callback=None,
) -> dict[tuple[str, str], str | None]:
    """Pre-classify all jobs that need LLM in batches.

    Walks raw_jobs once, identifies items needing LLM (not in standard set /
    keyword map / persistent cache), deduplicates, then calls _llm_classify_batch
    in batches of batch_size.

    Non-generic results are written to the persistent _llm_cache.
    Generic results (e.g. "技术类-软件") are returned in a per-run dict keyed by
    (raw_lower, title), since each title needs its own classification.

    Args:
        raw_jobs: list of raw job dicts.
        batch_size: number of jobs per LLM call (default 32).
        progress_callback: optional callable(done, total) for progress reporting.

    Returns:
        generic_cache dict — pass to normalize_category/normalize_job.
    """
    generic_cache: dict[tuple[str, str], str | None] = {}

    pending: list[dict] = []
    pending_keys_seen: set = set()

    for raw_job in raw_jobs:
        raw_cat = raw_job.get("category", "") or ""
        if not raw_cat:
            continue
        title = raw_job.get("title", "") or ""
        responsibilities = raw_job.get("responsibilities", "") or ""
        raw_lower = raw_cat.strip().lower()
        is_generic = _is_generic_category(raw_lower)

        if is_generic:
            # Generic: dedupe by (raw_lower, title)
            if not title and not responsibilities:
                continue  # skip — can't classify without context
            key = (raw_lower, title)
            if key in pending_keys_seen:
                continue
            pending_keys_seen.add(key)
            pending.append({
                "key": key,
                "is_generic": True,
                "raw_category": raw_cat,
                "title": title,
                "responsibilities": responsibilities,
            })
        else:
            # Non-generic: skip if already resolvable from standard / keyword / cache
            if raw_cat in STANDARD_CATEGORIES:
                continue
            if _KEYWORD_MAP.get(raw_lower):
                continue
            with _cache_lock:
                if raw_lower in _llm_cache:
                    continue
            if raw_lower in pending_keys_seen:
                continue
            pending_keys_seen.add(raw_lower)
            pending.append({
                "key": raw_lower,
                "is_generic": False,
                "raw_category": raw_cat,
                "title": title,
                "responsibilities": responsibilities,
            })

    total = len(pending)
    if total == 0:
        return generic_cache

    logger.info(
        f"prebatch_classify: {total} unique items need LLM (batch_size={batch_size})"
    )

    done = 0
    for i in range(0, total, batch_size):
        batch = pending[i:i + batch_size]
        results = _llm_classify_batch(batch)
        for item, result in zip(batch, results):
            if item["is_generic"]:
                generic_cache[item["key"]] = result
            else:
                with _cache_lock:
                    _llm_cache[item["key"]] = result
        # Persist after each batch
        with _cache_lock:
            _save_cache()
        done += len(batch)
        if progress_callback:
            progress_callback(done, total)

    return generic_cache


def normalize_category(
    raw_category: str,
    title: str = "",
    responsibilities: str = "",
    generic_cache: dict[tuple[str, str], str | None] | None = None,
) -> str | None:
    """Normalize a raw category string to one of the 15 standard categories.

    Args:
        raw_category: The raw category value (may be readable text OR an opaque code).
        title: Job title, used as context for LLM classification.
        responsibilities: Job responsibilities, used as context for LLM classification.
        generic_cache: Optional dict from prebatch_classify for generic categories.

    Returns:
        Standard category name, or None if non-tech.
    """
    if not raw_category:
        return None

    raw_lower = raw_category.strip().lower()
    is_generic = _is_generic_category(raw_lower)

    # For generic categories (e.g. "技术类", "技术类-软件"), the category alone
    # doesn't determine the standard class — the answer depends on the title.
    # Skip keyword/cache lookup entirely and go straight to LLM with full context.
    if is_generic:
        if not title and not responsibilities:
            logger.warning(
                f"Generic category '{raw_category}' has no title/responsibilities context, "
                "cannot classify reliably."
            )
            return None
        # Check pre-batched generic cache first (populated by prebatch_classify)
        if generic_cache is not None:
            key = (raw_lower, title)
            if key in generic_cache:
                return generic_cache[key]
        # Fallback: single-call LLM (slow path)
        logger.info(
            f"Generic category '{raw_category}' — calling LLM with title='{title[:40]}'"
        )
        return _llm_classify(raw_category, title=title, responsibilities=responsibilities)

    # Step 1: Direct match in standard categories
    if raw_category in STANDARD_CATEGORIES:
        return raw_category

    # Step 2: Keyword map lookup
    mapped = _KEYWORD_MAP.get(raw_lower)
    if mapped:
        return mapped

    # Step 3: Check LLM cache (keyed by raw value, works for both text and codes)
    with _cache_lock:
        if raw_lower in _llm_cache:
            return _llm_cache[raw_lower]

    # Step 4: LLM fallback (slow path — prebatch_classify should have handled this)
    logger.info(f"Category '{raw_category}' not in mapping, calling LLM with context...")
    result = _llm_classify(raw_category, title=title, responsibilities=responsibilities)

    # Cache the result (keyed by raw category value, including codes)
    with _cache_lock:
        _llm_cache[raw_lower] = result
        _save_cache()

    if result:
        logger.info(f"LLM mapped '{raw_category}' → '{result}'")
    else:
        logger.info(f"LLM classified '{raw_category}' as non-tech")

    return result
