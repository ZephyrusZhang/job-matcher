import { Router } from 'express';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ok } from '../helpers/response.js';
import { loadJobs } from '../data/transform.js';

const router = Router();

router.get('/companies', (_req, res) => {
  const companiesPath = join(import.meta.dirname ?? __dirname, '..', 'data', 'companies.json');
  const companies = JSON.parse(readFileSync(companiesPath, 'utf-8')) as any[];
  const jobs = loadJobs();

  const result = companies.map((c: any) => ({
    ...c,
    last_crawled_at: new Date(Date.now() - Math.floor(Math.random() * 3600000)).toISOString(),
    job_count: jobs.filter((j) => j.company.id === c.id).length,
  }));

  res.json(ok(result));
});

export default router;
