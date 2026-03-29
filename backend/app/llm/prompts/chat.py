"""Prompt template for follow-up chat conversations."""

import json

_SYSTEM_TEMPLATE = """你是一位资深技术招聘顾问，正在为用户提供岗位咨询。
你拥有用户的简历信息、岗位偏好、已生成的分析报告以及候选岗位的详细信息。
请基于这些上下文回答用户的问题。回答要具体、有针对性，避免泛泛而谈。

上下文：
- 用户简历：{parsed_resume}
- 用户偏好：{preferences}
- 已生成报告：{report_content}
- 候选岗位详情：{jobs_detail}"""


def build_chat_system_message(
    parsed_resume: dict,
    preferences: dict,
    report_content: str,
    jobs_detail: list[dict],
) -> dict:
    content = _SYSTEM_TEMPLATE.format(
        parsed_resume=json.dumps(parsed_resume, ensure_ascii=False),
        preferences=json.dumps(preferences, ensure_ascii=False),
        report_content=report_content,
        jobs_detail=json.dumps(jobs_detail, ensure_ascii=False),
    )
    return {"role": "system", "content": content}
