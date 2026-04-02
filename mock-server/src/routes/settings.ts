import { Router } from 'express';
import { ok } from '../helpers/response.js';
import { store } from '../store.js';

const router = Router();

// GET /settings — get current settings
router.get('/settings', (_req, res) => {
  res.json(ok(store.settings));
});

// PATCH /settings — update settings
router.patch('/settings', (req, res) => {
  const updates = req.body as Record<string, any>;
  Object.assign(store.settings, updates);
  res.json(ok(store.settings));
});

export default router;
