"""Prompt template for resume structured parsing."""

_SYSTEM_PROMPT = """你是一个简历解析器。你将收到一份简历的纯文本内容。

任务：提取以下结构化信息：
- skills: 技术技能列表（string array，如 ["React", "TypeScript", "Python"]）
- experience_years: 工作经验年限（integer，无法确定则为 null）
- education: 最高学历及专业（如 "本科 计算机科学"，无法确定则为 null）

请严格以 JSON 格式输出：
{"skills": [...], "experience_years": N, "education": "..."}"""


def build_parse_resume_messages(raw_text: str) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"简历内容：\n{raw_text}"},
    ]
