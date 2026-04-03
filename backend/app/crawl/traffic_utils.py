import json
import re


# ── 响应体截断 ──

def _estimate_size(obj) -> int:
    """Fast estimate of JSON serialized size without actually serializing."""
    if obj is None or isinstance(obj, bool):
        return 5
    if isinstance(obj, (int, float)):
        return 8
    if isinstance(obj, str):
        return len(obj) + 2
    if isinstance(obj, list):
        return sum(_estimate_size(item) for item in obj) + 2 * len(obj)
    if isinstance(obj, dict):
        return sum(len(k) + _estimate_size(v) + 4 for k, v in obj.items())
    return 10


# Arrays smaller than this are considered "reference/enum data" and kept intact.
# Typical enum: 15 categories × ~100 chars each ≈ 1500 chars — well under threshold.
# Typical job list: 20 jobs × ~2000 chars each ≈ 40000 chars — well over threshold.
_SMALL_ARRAY_THRESHOLD = 5000


def truncate_response(obj, max_array_items=2, max_str_len=200, max_depth=5, _depth=0):
    """
    截断策略：
    - 小体积数组（枚举/字典/映射表）：完整保留，不截断
    - 大体积对象数组（岗位列表等）：保留前 N 项 + 总数标注
    - 长字符串：截断到 200 字符 + 总长度标注
    - 嵌套深度 > 5 层：用类型摘要替代
    - 原始类型：原样保留
    """
    if _depth > max_depth:
        if isinstance(obj, dict):
            return f"{{...{len(obj)} fields}}"
        if isinstance(obj, list):
            return f"[...{len(obj)} items]"
        return obj

    if isinstance(obj, list):
        total = len(obj)
        if total == 0:
            return []

        is_struct_array = isinstance(obj[0], dict) and len(obj[0]) >= 3
        if is_struct_array:
            array_size = _estimate_size(obj)
            if array_size <= _SMALL_ARRAY_THRESHOLD:
                # Small array (enum/dict/mapping): keep ALL items, recurse into each
                return [
                    truncate_response(item, max_array_items, max_str_len, max_depth, _depth + 1)
                    for item in obj
                ]
            else:
                # Large array (job listings etc.): truncate to first N items
                keep = max_array_items
                truncated = [
                    truncate_response(item, max_array_items, max_str_len, max_depth, _depth + 1)
                    for item in obj[:keep]
                ]
                if total > keep:
                    truncated.append(f"... 共 {total} 条，已省略 {total - keep} 条")
                return truncated
        else:
            # Non-struct array (primitives, short arrays): keep more items
            keep = min(total, 5)
            truncated = [
                truncate_response(item, max_array_items, max_str_len, max_depth, _depth + 1)
                for item in obj[:keep]
            ]
            if total > keep:
                truncated.append(f"... 共 {total} 条，已省略 {total - keep} 条")
            return truncated

    if isinstance(obj, dict):
        return {
            k: truncate_response(v, max_array_items, max_str_len, max_depth, _depth + 1)
            for k, v in obj.items()
        }

    if isinstance(obj, str) and len(obj) > max_str_len:
        return obj[:max_str_len] + f"...({len(obj)}字符)"

    return obj


# ── 结构摘要 ──

def summarize_structure(obj, depth=0):
    """只返回 JSON 的 key 结构，不返回值"""
    if depth > 2:
        return "..."
    if isinstance(obj, dict):
        return {k: summarize_structure(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict):
            return [summarize_structure(obj[0], depth + 1), f"...共{len(obj)}条"]
        return f"[{len(obj)} items]"
    return type(obj).__name__


# ── 请求头过滤 ──

USEFUL_HEADERS = {
    "content-type", "accept", "authorization", "cookie",
    "referer", "origin", "user-agent",
    "x-csrf-token", "x-requested-with", "x-bogus", "x-s",
}


def filter_headers(headers: dict) -> dict:
    return {k: v for k, v in headers.items() if k.lower() in USEFUL_HEADERS}


# ── API 评分 ──

# 招聘相关关键词
_JOB_KEYWORDS = re.compile(
    r"(job|position|career|recruit|hire|vacancy|posting|"
    r"岗位|职位|招聘|校招|社招|实习)",
    re.I,
)

# 列表/分页相关关键词
_LIST_KEYWORDS = re.compile(
    r"(list|search|query|page|offset|limit|result|"
    r"列表|搜索|查询)",
    re.I,
)


def score_api(record: dict) -> int:
    """
    对捕获的 API 请求评分（0-10），评分越高越可能是岗位数据接口。

    评分维度：
    - 响应大小（大响应更可能是数据接口）
    - URL 路径是否包含招聘关键词
    - 响应中是否包含结构化列表
    - 请求方法（POST 通常是搜索/查询接口）
    """
    score = 0
    url = record.get("url", "")
    path = record.get("path", "")
    size = record.get("response_size", 0)
    method = record.get("method", "GET")
    preview = record.get("response_body_preview", {})

    # 响应大小
    if size > 10000:
        score += 3
    elif size > 2000:
        score += 2
    elif size > 500:
        score += 1

    # 路径关键词
    if _JOB_KEYWORDS.search(path) or _JOB_KEYWORDS.search(url):
        score += 3
    if _LIST_KEYWORDS.search(path) or _LIST_KEYWORDS.search(url):
        score += 1

    # 包含结构化列表
    if has_struct_list(preview):
        score += 2

    # POST 请求（查询接口常用 POST）
    if method == "POST":
        score += 1

    return min(score, 10)


def has_struct_list(obj) -> bool:
    """检查 JSON 对象中是否包含结构化对象数组（>=3 个字段的对象组成的数组）"""
    if isinstance(obj, list):
        if len(obj) >= 1 and isinstance(obj[0], dict) and len(obj[0]) >= 3:
            return True
    if isinstance(obj, dict):
        for v in obj.values():
            if has_struct_list(v):
                return True
    return False
