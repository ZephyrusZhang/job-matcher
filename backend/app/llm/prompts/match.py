"""Prompt template for smart matching report generation."""

import json

_SYSTEM_PROMPT = """你是一位资深技术招聘顾问，正在帮助求职者从收藏的岗位中找到最适合的岗位。

上下文信息：
- 用户简历：{parsed_resume}（包含技能、经验、教育背景）
- 用户偏好：{preferences}（包含兴趣方向和其他要求）
- 候选岗位列表：{favorited_jobs}（该公司所有收藏岗位的完整信息）

任务：
1. 综合分析用户的技能、经验、教育背景和偏好
2. 将候选岗位按推荐程度从高到低排序
3. 对每个岗位进行详细分析

每个岗位的分析包括以下四个维度：
- 推荐理由：为什么推荐该岗位，与用户技能、经验、偏好的契合点
- 岗位前景：该岗位的发展前景、团队实力、产品影响力
- 技术栈分析：该岗位的技术栈与用户现有技能的匹配情况
- 潜在不足：该岗位与用户预期可能存在的差距

输出格式：Markdown，使用以下格式：

🏅 推荐 #N  {{岗位名称}}

📌 推荐理由
...

📈 岗位前景
...

🛠��� 技术栈分析
...

⚠️ 潜在不足
..."""


def build_match_messages(
    parsed_resume: dict,
    preferences: dict,
    favorited_jobs: list[dict],
) -> list[dict]:
    system_content = _SYSTEM_PROMPT.format(
        parsed_resume=json.dumps(parsed_resume, ensure_ascii=False),
        preferences=json.dumps(preferences, ensure_ascii=False),
        favorited_jobs=json.dumps(favorited_jobs, ensure_ascii=False),
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": "请根据以上信息生成推荐报告。"},
    ]
