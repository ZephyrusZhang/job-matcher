import { Router } from 'express';
import { ok, err } from '../helpers/response.js';
import { store } from '../store.js';
import { loadJobs } from '../data/transform.js';

const router = Router();

// POST /favorites — add favorite
router.post('/favorites', (req, res) => {
  const { job_id } = req.body as { job_id?: string };
  if (!job_id) {
    res.status(400).json(err('INVALID_PARAM', 'job_id is required'));
    return;
  }

  const jobs = loadJobs();
  const job = jobs.find((j) => j.id === job_id);
  if (!job) {
    res.status(404).json(err('NOT_FOUND', 'Job not found'));
    return;
  }

  store.favorites.add(job_id);
  res.json(ok({ job_id, is_favorited: true }));
});

// DELETE /favorites/:jobId — remove favorite
router.delete('/favorites/:jobId', (req, res) => {
  const { jobId } = req.params;
  store.favorites.delete(jobId);
  res.json(ok({ job_id: jobId, is_favorited: false }));
});

// GET /favorites — list favorites
router.get('/favorites', (req, res) => {
  const jobs = loadJobs();
  const companyId = req.query.company_id as string | undefined;

  let favorited = jobs
    .filter((j) => store.favorites.has(j.id))
    .map((j) => ({
      job_id: j.id,
      title: j.title,
      category: j.category,
      company_name: j.company.name,
      location: j.location,
      favorited_at: new Date().toISOString(),
    }));

  if (companyId) {
    const favJobs = jobs.filter((j) => store.favorites.has(j.id) && j.company.id === companyId);
    favorited = favJobs.map((j) => ({
      job_id: j.id,
      title: j.title,
      category: j.category,
      company_name: j.company.name,
      location: j.location,
      favorited_at: new Date().toISOString(),
    }));
  }

  res.json(ok(favorited));
});

// GET /favorites/summary — count per company
router.get('/favorites/summary', (_req, res) => {
  const jobs = loadJobs();
  const counts: Record<string, { company_id: string; company_name: string; count: number }> = {};

  for (const id of store.favorites) {
    const job = jobs.find((j) => j.id === id);
    if (job) {
      if (!counts[job.company.id]) {
        counts[job.company.id] = { company_id: job.company.id, company_name: job.company.name, count: 0 };
      }
      counts[job.company.id]!.count++;
    }
  }

  res.json(ok(Object.values(counts)));
});

export default router;
