import { Router } from 'express';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ok, err } from '../helpers/response.js';
import { streamMarkdown } from '../helpers/sse.js';
import { store } from '../store.js';

const router = Router();

// POST /compare/generate — SSE stream preset comparison report
router.post('/compare/generate', async (req, res) => {
  if (!store.resume) {
    res.status(400).json(err('NO_RESUME', 'Please upload a resume first'));
    return;
  }

  const { company_id } = req.body as { company_id?: string };
  const key = `${company_id ?? 'all'}_compare`;

  const mdPath = join(import.meta.dirname ?? __dirname, '..', 'data', 'report-compare.md');
  const markdown = readFileSync(mdPath, 'utf-8');

  // Store the report
  store.reports.set(key, {
    id: key,
    type: 'compare',
    company_id: company_id ?? null,
    content: markdown,
    created_at: new Date().toISOString(),
  });

  await streamMarkdown(res, markdown);
});

// GET /compare/report — get generated report
router.get('/compare/report', (req, res) => {
  const companyId = req.query.company_id as string | undefined;
  const key = `${companyId ?? 'all'}_compare`;

  const report = store.reports.get(key);
  if (!report) {
    res.status(404).json(err('NO_REPORT', 'Report not found. Generate one first.'));
    return;
  }

  res.json(ok(report));
});

export default router;
