SYSTEM_PROMPT = """你是一个岗位信息结构化解析器。你将收到某公司招聘页面的原始文本内容。

任务：
1. 识别并提取所有技术研发类岗位
2. 过滤非技术岗位（产品、设计、运营、市场、HR、财务等）
3. 对每个技术岗位输出以下字段的 JSON：
   - title: 岗位名称
   - category: 岗位方向，必须从以下选项中选择：
     算法/后端/客户端/前端/测试/大数据/安全/硬件/机器学习/基础架构/多媒体/计算机视觉/运维/数据挖掘/自然语言处理
   - location: 工作地点（字符串；可能包含多个城市，用分隔符分开，由后端负责归一化为城市数组）
   - job_type: 实习/全职（只能是这两个值之一；兼职、合同工等统一归为 全职）
   - responsibilities: 核心职责描述
   - requirements_must: 必备技能列表（string array）
   - requirements_nice: 加分技能列表（string array）
   - department: 所属部门
   - department_product: 部门负责的产品
   - education: 学历要求
   - experience: 经验要求
   - posted_date: 发布日期（ISO date 格式，无法确定则为 null）
   - source_url: 原始链接
   - summary: 一句话概述（20字以内）

输出格式：
{{"jobs": [<Job>, <Job>, ...]}}

公司名称：{company_name}"""


def build_messages(raw_content: str, company_name: str) -> list[dict]:
    system = SYSTEM_PROMPT.format(company_name=company_name)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"原始内容：\n{raw_content}"},
    ]
