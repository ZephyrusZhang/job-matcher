import { Router } from 'express';
import multer from 'multer';
import { ok, err } from '../helpers/response.js';
import { store } from '../store.js';

const upload = multer({ storage: multer.memoryStorage() });
const router = Router();

// POST /resume/upload — upload resume (multipart/form-data)
router.post('/resume/upload', upload.single('file'), (req, res) => {
  const file = (req as any).file;
  if (!file) {
    res.status(400).json(err('NO_FILE', 'No file uploaded'));
    return;
  }

  // Simulate parsed resume
  store.resume = {
    filename: file.originalname,
    size: file.size,
    mime_type: file.mimetype,
    uploaded_at: new Date().toISOString(),
    parsed: {
      name: '张三',
      email: 'zhangsan@example.com',
      phone: '138****1234',
      education: '计算机科学与技术 - 硕士',
      experience_years: 3,
      skills: ['Go', 'Python', 'TypeScript', 'React', 'Kubernetes', 'Docker', 'PostgreSQL'],
      summary: '3年后端开发经验，熟悉分布式系统设计和云原生技术栈。',
    },
  };

  // Cascade clear reports and chat history
  store.reports.clear();
  store.chatHistory.clear();

  res.json(ok(store.resume));
});

// GET /resume — get current resume
router.get('/resume', (_req, res) => {
  if (!store.resume) {
    res.status(404).json(err('NO_RESUME', 'No resume uploaded'));
    return;
  }
  res.json(ok(store.resume));
});

// DELETE /resume — delete resume + cascade clear
router.delete('/resume', (_req, res) => {
  store.resume = null;
  store.reports.clear();
  store.chatHistory.clear();
  res.json(ok({ deleted: true }));
});

export default router;
