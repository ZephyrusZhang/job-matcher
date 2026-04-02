import { Router } from 'express';
import { ok, err } from '../helpers/response.js';
import { setupSSE } from '../helpers/sse.js';
import { store } from '../store.js';

const router = Router();

const PRESET_REPLIES: Record<string, string> = {
  default: `好的，我来为您详细分析一下。

根据您的简历和目标岗位，我有以下几点建议：

1. **技术匹配度**：您的核心技术栈与目标岗位的要求匹配度较高，特别是在后端开发和分布式系统方面。

2. **建议补充的技能**：建议您在面试前重点准备以下内容：
   - 系统设计面试：重点复习分布式缓存、消息队列、微服务架构
   - 算法与数据结构：LeetCode 中等难度以上的题目
   - 项目经验包装：准备 STAR 格式的项目描述

3. **简历优化建议**：
   - 量化您的项目成果（如 QPS、延迟优化比例等）
   - 突出您在团队协作中的角色和贡献
   - 添加技术博客或开源项目的链接

如果您有更具体的问题，欢迎继续提问！`,
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// POST /chat/message — SSE stream reply
router.post('/chat/message', async (req, res) => {
  const { report_id, message } = req.body as { report_id?: string; message?: string };

  if (!report_id || !message) {
    res.status(400).json(err('INVALID_PARAM', 'report_id and message are required'));
    return;
  }

  // Store user message
  const history = store.chatHistory.get(report_id) ?? [];
  history.push({ role: 'user', content: message, timestamp: new Date().toISOString() });

  const reply = PRESET_REPLIES.default!;

  // Stream the reply via SSE
  setupSSE(res);

  const chunks = reply.split(/\n\n/).filter((c) => c.trim().length > 0);
  for (const chunk of chunks) {
    res.write(`data: ${JSON.stringify({ content: chunk + '\n\n' })}\n\n`);
    await sleep(100);
  }

  res.write(`data: [DONE]\n\n`);
  res.end();

  // Store assistant message
  history.push({ role: 'assistant', content: reply, timestamp: new Date().toISOString() });
  store.chatHistory.set(report_id, history);
});

// GET /chat/history — get chat history
router.get('/chat/history', (req, res) => {
  const reportId = req.query.report_id as string | undefined;

  if (!reportId) {
    res.status(400).json(err('INVALID_PARAM', 'report_id is required'));
    return;
  }

  const history = store.chatHistory.get(reportId) ?? [];
  res.json(ok(history));
});

export default router;
