"""
根据拦截到的请求数据生成 Claude 提示词（支持两阶段：列表页 + 详情页）
用法: python build_prompt.py [--input ./generated/captured_requests.json] [--url <target_url>]
"""

import argparse
import json
import sys
from pathlib import Path


# ---- 输出目录 ----
GENERATED_DIR = Path("./generated")


def filter_relevant(captured: list[dict]) -> list[dict]:
    """过滤出与业务数据相关的请求"""
    relevant = []
    for entry in captured:
        body = entry.get("response_body")
        if not body:
            continue
        if isinstance(body, str) and body.strip().startswith("<!"):
            continue
        if entry.get("status", 0) != 200:
            continue
        # 跳过埋点回执（字段数 ≤3 且全是埋点标记字段）
        if isinstance(body, dict) and len(body) <= 3:
            keys = set(body.keys())
            if keys <= {"e", "sc", "tc", "web_id", "ssid"}:
                continue
        relevant.append(entry)
    return relevant


def truncate_body(body, max_items: int = 3, max_chars: int = 4000) -> str:
    """截断响应体，保留结构但控制大小"""
    if isinstance(body, dict):
        truncated = {}
        for k, v in body.items():
            if isinstance(v, list) and len(v) > max_items:
                truncated[k] = {
                    "_type": "array",
                    "_total": len(v),
                    "_sample": v[:max_items],
                }
            else:
                truncated[k] = v
        result = json.dumps(truncated, ensure_ascii=False, indent=2)
    elif isinstance(body, str):
        result = body
    else:
        result = json.dumps(body, ensure_ascii=False, indent=2)

    if len(result) > max_chars:
        result = result[:max_chars] + "\n... (已截断)"
    return result


def format_request(entry: dict, index: int) -> str:
    """格式化单个请求为文本"""
    phase_label = "列表页" if entry.get("phase") == "list" else "详情页"
    text = f"""
--- 请求 #{index} [{phase_label}] ---
URL: {entry['url']}
Method: {entry['method']}
Status: {entry['status']}
"""
    keep = {
        "content-type", "accept", "authorization",
        "cookie", "referer", "origin", "x-requested-with",
    }
    headers = {
        k: v for k, v in entry.get("request_headers", {}).items()
        if k.lower() in keep
    }
    if headers:
        text += f"Request Headers: {json.dumps(headers, ensure_ascii=False)}\n"

    if entry.get("post_data"):
        text += f"POST Body: {entry['post_data'][:1500]}\n"

    body = entry.get("response_body")
    if body:
        text += f"Response Body:\n{truncate_body(body)}\n"

    return text


def build_prompt(captured: list[dict], target_url: str) -> str:
    relevant = filter_relevant(captured)

    # 按阶段分组
    list_reqs = [r for r in relevant if r.get("phase") == "list"]
    detail_reqs = [r for r in relevant if r.get("phase") == "detail"]
    has_detail_phase = len(detail_reqs) > 0

    # 拼接请求信息
    requests_text = ""
    idx = 1

    if list_reqs:
        requests_text += "\n### 列表页请求\n"
        for entry in list_reqs:
            requests_text += format_request(entry, idx)
            idx += 1

    if detail_reqs:
        requests_text += "\n### 详情页请求（点击岗位卡片后触发）\n"
        for entry in detail_reqs:
            requests_text += format_request(entry, idx)
            idx += 1

    # 兼容旧格式（无 phase 字段）
    if not list_reqs and not detail_reqs:
        for entry in relevant:
            requests_text += format_request(entry, idx)
            idx += 1

    # ---- 根据是否有详情页请求，生成不同的提示 ----
    if has_detail_phase:
        detail_instruction = """
## 重要：两阶段请求说明

拦截数据分为两个阶段：
- **列表页请求**：打开岗位列表页时自动触发的 API，通常返回岗位列表（可能包含也可能不包含详细的职责和要求）
- **详情页请求**：点击某个岗位卡片后触发的 API，通常返回该岗位的完整详情

请你判断：
1. 如果**列表页 API 已经返回了完整的岗位信息**（包含职责描述、技术要求等），则爬虫只需调用列表 API 即可，无需请求详情 API
2. 如果**列表页 API 只返回了摘要信息**（仅有标题、地点等，缺少职责和要求），则爬虫需要：先通过列表 API 获取所有岗位 ID，再逐个请求详情 API 获取完整信息

在代码中请根据你的判断选择合适的策略，并在 API 分析中说明理由。"""
    else:
        detail_instruction = """
## 注意

拦截数据仅包含列表页请求。如果列表 API 的响应中**缺少岗位职责和要求等详细信息**，请根据 API 的 URL 模式推断可能的详情 API 路径（通常是列表 API 路径 + 岗位 ID），并在代码中实现详情页请求逻辑。"""

    prompt = f"""你是一个专业的爬虫工程师。我通过浏览器拦截了以下网页的所有 API 请求和响应。

目标页面: {target_url}

**注意：上述目标页面 URL 中包含用户指定的筛选参数（如岗位类型、工作地点、关键词等）。请仔细分析 URL 中的查询参数以及拦截到的 API 请求中对应的筛选字段，生成的爬虫代码必须携带这些相同的筛选条件，确保只爬取符合该筛选条件下的所有分页数据。**
{detail_instruction}

请分析这些请求，完成以下任务:

## 任务

1. **识别核心 API**: 从拦截到的请求中，找出用于获取岗位列表和岗位详情的 API 接口
2. **提取筛选参数**: 从目标页面 URL 和 API 请求参数中，识别出用户设置的筛选条件，并在生成的代码中保留这些条件
3. **分析数据结构**: 分析响应数据的 JSON 结构，确定哪些字段包含我们需要的岗位信息
4. **生成爬虫代码**: 生成一个完整的 Python 爬虫脚本

## 爬虫代码要求

- 使用 `httpx` 作为 HTTP 客户端（支持异步）
- **必须携带目标页面 URL 中的筛选参数**，将其作为 API 请求参数传递，确保爬取结果与用户在浏览器中看到的筛选结果一致
- 将筛选参数提取为脚本顶部的常量，方便后续修改
- 实现翻页逻辑，爬取该筛选条件下的**所有分页**数据
- 如果列表 API 不包含岗位描述等详细信息，需要额外请求详情 API
- 加入合理的请求间隔（1-3秒）和错误重试
- 将结果保存为 JSON 文件
- 代码中包含必要的请求头（从拦截数据中提取）
- 添加清晰的中文注释

## 输出数据格式（严格遵守）

每条岗位数据**必须**保存为以下 JSON 结构，字段名和层级不得修改。如果某个字段在 API 响应中没有直接对应，则填 `null`：

```json
{{
  "title": "岗位名称 - 职位标题",
  "category": "岗位方向 - 所属技术方向（如算法、后端、前端、机器学习等）",
  "location": "工作地点 - 城市 / 远程 / 混合办公",
  "job_type": "岗位类型 - 如 intern / full-time / part-time / contract",
  "responsibilities": "核心职责 - 岗位的主要工作内容描述（保留原文换行）",
  "requirements": "技术要求 - 必备技能与加分技能（保留原文换行）",
  "department": "所属部门 - 该岗位所在的业务部门缩写或代号",
  "department_product": "部门产品 - 该部门负责的主要产品或业务线全称",
  "education": "学历要求 - 最低学历要求",
  "experience": "经验要求 - 所需工作经验描述",
  "posted_date": "发布日期 - 岗位上线时间（ISO 格式或原始格式）",
  "source_url": "原始链接 - 跳转至公司官方招聘页面的链接",
  "summary": "一句话总结 - 用简短的一句话概括该岗位的核心内容"
}}
```

最终输出的 JSON 文件格式为：

```json
{{
  "company": "公司名称",
  "crawl_time": "爬取时间 ISO 格式",
  "total": 123,
  "jobs": [ ... ]
}}
```

## 输出格式

请按以下顺序输出：

### 1. API 分析
简要说明你识别出的 API 端点及其作用。说明列表 API 是否已包含完整岗位信息，还是需要额外请求详情 API。

### 2. 筛选参数分析
列出从目标页面 URL 和 API 请求中提取的筛选参数，说明每个参数的含义和取值。

### 3. 数据结构分析
说明 API 响应字段与上述目标字段的映射关系。对于 API 中没有直接提供的字段，说明是否可以从其他字段推断。

### 4. 完整爬虫代码
可直接运行的 Python 脚本。

## 拦截到的请求数据

共 {len(relevant)} 个相关请求（列表页 {len(list_reqs)} 个，详情页 {len(detail_reqs)} 个）:

{requests_text}"""

    return prompt


def main():
    parser = argparse.ArgumentParser(description="生成 Claude 提示词（支持两阶段数据）")
    parser.add_argument("--input", default=None, help="拦截数据文件（默认 ./generated/captured_requests.json）")
    parser.add_argument("--url", default="", help="目标页面 URL")
    parser.add_argument("--output", default=None, help="输出文件（默认 ./generated/prompt.txt）")
    args = parser.parse_args()

    input_path = Path(args.input) if args.input else GENERATED_DIR / "captured_requests.json"
    output_path = Path(args.output) if args.output else GENERATED_DIR / "prompt.txt"

    if not input_path.exists():
        print(f"错误: {input_path} 不存在，请先运行 interceptor.py")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        captured = json.load(f)

    target_url = args.url or "(未指定)"
    prompt = build_prompt(captured, target_url)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(prompt)

    relevant = filter_relevant(captured)
    list_count = sum(1 for r in relevant if r.get("phase") == "list")
    detail_count = sum(1 for r in relevant if r.get("phase") == "detail")
    print(f"原始请求: {len(captured)} 条")
    print(f"有效请求: {len(relevant)} 条（列表页 {list_count} + 详情页 {detail_count}）")
    print(f"Prompt 长度: {len(prompt)} 字符")
    print(f"已保存到: {output_path}")


if __name__ == "__main__":
    main()