import type { Response } from 'express';

export function setupSSE(res: Response) {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function streamMarkdown(res: Response, markdown: string, delayMs: number = 100) {
  setupSSE(res);

  // Split by double newline (paragraphs)
  const chunks = markdown.split(/\n\n/).filter((c) => c.trim().length > 0);

  for (const chunk of chunks) {
    res.write(`data: ${JSON.stringify({ content: chunk + '\n\n' })}\n\n`);
    await sleep(delayMs);
  }

  res.write(`data: [DONE]\n\n`);
  res.end();
}
