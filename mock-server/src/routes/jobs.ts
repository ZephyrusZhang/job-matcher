import { Router } from 'express';
import { ok, err } from '../helpers/response.js';
import { paginate } from '../helpers/pagination.js';
import { loadJobs, type TransformedJob } from '../data/transform.js';
import { store } from '../store.js';

const router = Router();

// GET /jobs/search — keyword search (must be before /jobs/:id)
router.get('/jobs/search', (req, res) => {
  const q = (req.query.q as string || '').toLowerCase();
  if (!q) {
    res.json(ok([]));
    return;
  }

  const jobs = loadJobs();
  const page = parseInt(req.query.page as string) || 1;
  const pageSize = parseInt(req.query.page_size as string) || 20;

  const matched = jobs.filter((j) => {
    const text = `${j.title} ${j.responsibilities} ${j.requirements.must_have.join(' ')} ${j.requirements.nice_to_have.join(' ')}`.toLowerCase();
    return text.includes(q);
  }).map((j) => ({ ...j, is_favorited: store.favorites.has(j.id) }));

  const result = paginate(matched, page, pageSize);
  res.json(ok(result.data, result.pagination));
});

// GET /jobs/suggest — autocomplete
router.get('/jobs/suggest', (req, res) => {
  const q = (req.query.q as string || '').toLowerCase();
  if (!q) {
    res.json(ok([]));
    return;
  }

  const jobs = loadJobs();
  const suggestions = new Set<string>();

  for (const job of jobs) {
    if (job.title.toLowerCase().includes(q)) suggestions.add(job.title);
    if (job.category.toLowerCase().includes(q)) suggestions.add(job.category);
    if (suggestions.size >= 10) break;
  }

  res.json(ok([...suggestions]));
});

// GET /jobs/:id — single job detail
router.get('/jobs/:id', (req, res) => {
  const jobs = loadJobs();
  const job = jobs.find((j) => j.id === req.params.id);

  if (!job) {
    res.status(404).json(err('NOT_FOUND', 'Job not found'));
    return;
  }

  res.json(ok({ ...job, is_favorited: store.favorites.has(job.id) }));
});

// GET /jobs — list with filters, pagination, sorting
router.get('/jobs', (req, res) => {
  let jobs = loadJobs();

  // Filters
  const { company_id, category, location, job_type, posted_within, sort_by, sort_order } = req.query as Record<string, string>;

  if (company_id) jobs = jobs.filter((j) => j.company.id === company_id);
  if (category) {
    const cats = category.split(',');
    jobs = jobs.filter((j) => cats.includes(j.category));
  }
  if (location) jobs = jobs.filter((j) => j.location.includes(location));
  if (job_type) jobs = jobs.filter((j) => j.job_type === job_type);
  if (posted_within) {
    let hours = 0;
    if (posted_within.endsWith('h')) hours = parseInt(posted_within);
    else if (posted_within.endsWith('d')) hours = parseInt(posted_within) * 24;
    if (hours > 0) {
      const cutoff = new Date(Date.now() - hours * 3600000).toISOString().split('T')[0]!;
      jobs = jobs.filter((j) => j.posted_date >= cutoff);
    }
  }

  // Sorting
  if (sort_by) {
    const order = sort_order === 'asc' ? 1 : -1;
    jobs = [...jobs].sort((a, b) => {
      const aVal = (a as any)[sort_by] ?? '';
      const bVal = (b as any)[sort_by] ?? '';
      return aVal > bVal ? order : aVal < bVal ? -order : 0;
    });
  }

  // Inject favorites
  const withFav = jobs.map((j) => ({ ...j, is_favorited: store.favorites.has(j.id) }));

  // Pagination
  const page = parseInt(req.query.page as string) || 1;
  const pageSize = parseInt(req.query.page_size as string) || 20;
  const result = paginate(withFav, page, pageSize);

  res.json(ok(result.data, result.pagination));
});

export default router;
