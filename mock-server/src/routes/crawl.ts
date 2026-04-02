import { Router } from 'express';
import { ok, err } from '../helpers/response.js';
import { v4 as uuidv4 } from 'uuid';

const router = Router();

interface CrawlTask {
  id: string;
  company_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  jobs_found: number;
  started_at: string;
  completed_at: string | null;
}

const tasks: CrawlTask[] = [];

// POST /crawl/trigger — trigger a crawl task
router.post('/crawl/trigger', (req, res) => {
  const { company_id } = req.body as { company_id?: string };

  if (!company_id) {
    res.status(400).json(err('INVALID_PARAM', 'company_id is required'));
    return;
  }

  const task: CrawlTask = {
    id: uuidv4(),
    company_id,
    status: 'running',
    progress: 0,
    jobs_found: 0,
    started_at: new Date().toISOString(),
    completed_at: null,
  };

  tasks.push(task);

  // Simulate completion after a short delay
  setTimeout(() => {
    task.status = 'completed';
    task.progress = 100;
    task.jobs_found = Math.floor(Math.random() * 50) + 10;
    task.completed_at = new Date().toISOString();
  }, 3000);

  res.json(ok(task));
});

// GET /crawl/tasks — list all tasks
router.get('/crawl/tasks', (_req, res) => {
  res.json(ok(tasks));
});

// GET /crawl/tasks/:id — single task detail
router.get('/crawl/tasks/:id', (req, res) => {
  const task = tasks.find((t) => t.id === req.params.id);
  if (!task) {
    res.status(404).json(err('NOT_FOUND', 'Task not found'));
    return;
  }
  res.json(ok(task));
});

export default router;
