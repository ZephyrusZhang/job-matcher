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
    "广告": "算法",
    "智能创作": "算法",

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
    "工程类": "后端",

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
    "全栈": "前端",
    "全栈开发": "前端",
    "全栈开发工程师": "前端",

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

    # 宽泛分类词 → 映射到最近似的标准类别
    "技术类": "后端",
}

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


def _llm_classify(raw_category: str) -> str | None:
    """Use LLM to classify an unknown category. Returns standard category or None."""
    try:
        from openai import OpenAI
        from dotenv import load_dotenv
        load_dotenv()

        client = OpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        )
        model = os.getenv("LLM_MODEL", "deepseek-chat")

        categories_str = "、".join(STANDARD_CATEGORIES)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"你是一个岗位分类器。将输入的岗位类别名映射到以下标准类别之一：\n"
                        f"{categories_str}\n\n"
                        f"如果无法归类（非技术岗位），返回 null。\n"
                        f"只返回 JSON：{{\"category\": \"标准类别名\"}} 或 {{\"category\": null}}"
                    ),
                },
                {"role": "user", "content": raw_category},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=50,
        )
        result = json.loads(response.choices[0].message.content)
        mapped = result.get("category")
        if mapped and mapped in STANDARD_CATEGORIES:
            return mapped
        return None
    except Exception as e:
        logger.warning(f"LLM category classification failed for '{raw_category}': {e}")
        return None


def _looks_like_code(s: str) -> bool:
    """Detect if a string looks like an internal code rather than readable text.

    Examples of codes: "j1007", "10001", "R123", "tech_backend"
    Examples of readable: "后端开发", "算法", "Backend", "机器学习工程师"
    """
    import re
    # Contains any CJK character → readable
    if re.search(r"[\u4e00-\u9fff]", s):
        return False
    # Pure digits or letter+digits pattern → code
    if re.match(r"^[a-zA-Z]?\d+$", s.strip()):
        return True
    # Very short alphanumeric with underscores → likely code
    if re.match(r"^[a-zA-Z0-9_]{1,10}$", s.strip()) and not s.strip().isalpha():
        return True
    return False


def normalize_category(raw_category: str) -> str | None:
    """Normalize a raw category string to one of the 15 standard categories.

    Returns:
        Standard category name, or None if the category cannot be mapped
        (non-tech position).
    """
    if not raw_category:
        return None

    raw_lower = raw_category.strip().lower()

    # Step 0: If it looks like an internal code, skip entirely (don't cache)
    # The crawler should resolve codes to readable text before output.
    if _looks_like_code(raw_category):
        logger.warning(
            f"Category '{raw_category}' looks like an internal code, skipping. "
            "The crawler should resolve codes to readable text."
        )
        return None

    # Step 1: Direct match in standard categories
    if raw_category in STANDARD_CATEGORIES:
        return raw_category

    # Step 2: Keyword map lookup
    mapped = _KEYWORD_MAP.get(raw_lower)
    if mapped:
        return mapped

    # Step 3: Check LLM cache
    with _cache_lock:
        if raw_lower in _llm_cache:
            return _llm_cache[raw_lower]

    # Step 4: LLM fallback
    logger.info(f"Category '{raw_category}' not in mapping, calling LLM...")
    result = _llm_classify(raw_category)

    # Cache the result (including None for non-tech)
    with _cache_lock:
        _llm_cache[raw_lower] = result
        _save_cache()

    if result:
        logger.info(f"LLM mapped '{raw_category}' → '{result}'")
    else:
        logger.info(f"LLM could not classify '{raw_category}', marking as non-tech")

    return result
