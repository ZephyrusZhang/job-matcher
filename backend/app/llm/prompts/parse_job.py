"""Prompt template for job posting structured parsing."""

import json

_SYSTEM_PROMPT = """你是一个岗位信息结构化解析器。你将收到某公司招聘页面的原始文本内容。

任务：
1. 识别并提取所有技术研发类岗位
2. 过滤非技术岗位（产品、设计、运营、市场、HR、财务等）
3. 对每个技术岗位，仔细阅读其"职位描述"和"职位要求"两个部分，提取以下字段：

字段说明：
- title: 岗位名称
- category: 岗位方向，必须从以下选项中选择：
  算法/后端/客户端/前端/测试/大数据/安全/硬件/机器学习/基础架构/多媒体/计算机视觉/运维/数据挖掘/自然语言处理
- location: 工作地点
- job_type: fulltime/intern/parttime/contract
- responsibilities: 完整保留"职位描述"部分的全部内容，包括项目/计划说明（如"ByteIntern：面向...提供转正机会"）、团队介绍（如"团队介绍：..."）以及编号职责列表。不要省略、不要只提取编号条目，必须把"职位描述"标题下的所有文字都放进来
- requirements: 完整保留"职位要求"（或"任职要求""岗位要求"）部分的全部原始文本。保留编号和原文措辞，不要提取关键词、不要重组、不要省略任何条目。和 responsibilities 一样直接放原文
- department: 所属部门
- department_product: 部门负责的产品
- education: 学历要求
- experience: 经验要求
- posted_date: 发布日期（ISO date 格式，无法确定则为 null）
- source_url: 原始链接
- summary: 一句话概述（20字以内）

关键规则：
- responsibilities 和 requirements 都是直接保留原文，不做提取或重组。
- 学历和经验信息除了在 requirements 原文中保留外，还需要单独提取到 education 和 experience 字段。

请严格以 JSON 格式输出：
{"jobs": [<Job>, <Job>, ...]}"""


def build_parse_job_messages(raw_content: str, company_name: str) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"公司名称：{company_name}\n\n原始内容：\n{raw_content}",
        },
    ]
