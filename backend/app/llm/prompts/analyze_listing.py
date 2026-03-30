"""Prompt template for analyzing a job listing page structure."""

_SYSTEM_PROMPT = """你是一个网页结构分析专家。你将收到一个招聘网站列表页的 DOM 结构分析报告。

报告包含三部分：
1. **重复出现的链接组**：页面上相同 class 的 <a> 标签及其 href（出现多次的链接组很可能是岗位链接）
2. **重复出现的容器元素**：相同 class 的 li/div/article 等元素及其 HTML 样例（出现多次的容器很可能是岗位卡片）
3. **分页组件**：翻页区域的 HTML

你的任务：从中判断哪些是岗位卡片，如何跳转到岗位详情页，以及如何翻页。

## 岗位卡片判断规则

- 如果有一组 <a> 标签（出现 5 次以上），且 href 指向类似详情页的路径（包含 ID、position、detail、post 等），那这就是岗位链接。
  → card_strategy = "href"，job_card_selector 取该链接的选择器，job_links 列出所有 href
- 如果没有明显的 <a> 链接组，但有重复出现的 li/div 容器（出现 5 次以上），那这些是可点击的岗位卡片。
  → card_strategy = "click"，job_card_selector 取该容器的选择器，job_links 为空

## 翻页判断规则

从分页组件 HTML 中提取两个选择器：
1. **next_button_selector**："下一页"按钮或 ">" 箭头的 CSS 选择器。这是主要的翻页方式。
   例如分页 HTML 里有 `<a class="next">>`，则 next_button_selector = "a.next"
   例如有 `<li class="btn-next"><button>>`，则 next_button_selector = "li.btn-next button"
2. **page_number_selector**：页码数字元素的 CSS 选择器（所有页码共用的选择器）。这是备用翻页方式。
   例如 `<li class="number">1</li><li class="number">2</li>`，则 page_number_selector = "li.number"
   例如 `<a class="page-link">1</a><a class="page-link">2</a>`，则 page_number_selector = "a.page-link"

请严格以 JSON 格式输出：
{
  "job_links": ["href1", "href2", ...],
  "job_card_selector": "CSS选择器",
  "card_strategy": "href" 或 "click",
  "next_button_selector": "下一页按钮的CSS选择器或null",
  "page_number_selector": "页码数字元素的CSS选择器或null",
  "confidence": 0.0到1.0
}

关键要求：
- job_card_selector 必须是报告中实际出现的选择器，不要自己编造
- 如果 card_strategy 是 "href"，job_links 必须包含所有岗位详情页的 href 原文
- next_button_selector 和 page_number_selector 都必须从分页组件 HTML 中提取，不要编造"""


def build_analyze_listing_messages(
    page_text: str, page_url: str, html_snippet: str
) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"DOM 结构分析报告：\n{html_snippet}\n\n"
                f"页面文本内容（前2000字）：\n{page_text[:2000]}"
            ),
        },
    ]
